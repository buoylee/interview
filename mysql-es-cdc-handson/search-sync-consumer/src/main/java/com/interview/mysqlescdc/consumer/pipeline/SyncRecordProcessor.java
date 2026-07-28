package com.interview.mysqlescdc.consumer.pipeline;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import com.interview.mysqlescdc.consumer.canal.CanalRevisionParser;
import com.interview.mysqlescdc.consumer.canal.RevisionSignal;
import com.interview.mysqlescdc.consumer.dlq.DlqRecord;
import com.interview.mysqlescdc.consumer.dlq.DlqStore;
import com.interview.mysqlescdc.consumer.dlq.RecordDlqRecord;
import com.interview.mysqlescdc.consumer.dlq.RecordDlqStore;
import com.interview.mysqlescdc.consumer.failpoint.Failpoint;
import com.interview.mysqlescdc.consumer.failpoint.FailpointRegistry;
import com.interview.mysqlescdc.consumer.projection.SearchDocument;
import com.interview.mysqlescdc.consumer.projection.SearchDocumentProjector;
import com.interview.mysqlescdc.consumer.sink.BulkItemResult;
import com.interview.mysqlescdc.consumer.sink.BulkOutcome;
import com.interview.mysqlescdc.consumer.sink.BulkProtocolException;
import com.interview.mysqlescdc.consumer.sink.BulkTransportException;
import com.interview.mysqlescdc.consumer.sink.BulkWriteResult;
import com.interview.mysqlescdc.consumer.sink.ElasticsearchGateway;
import com.interview.mysqlescdc.consumer.source.SourceProductSnapshot;
import com.interview.mysqlescdc.consumer.source.SourceSnapshotRepository;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.json.JsonMapper;

@Component
public class SyncRecordProcessor {
    private static final int PARSE_ATTEMPTS = 3;

    private final CanalRevisionParser parser;
    private final SourceSnapshotRepository source;
    private final SearchDocumentProjector projector;
    private final ElasticsearchGateway elasticsearch;
    private final DlqStore productDlq;
    private final RecordDlqStore recordDlq;
    private final FailpointRegistry failpoints;
    private final String targetAlias;
    private final int retryAttempts;
    private final JsonMapper json = JsonMapper.builder().build();

    public SyncRecordProcessor(
            CanalRevisionParser parser,
            SourceSnapshotRepository source,
            SearchDocumentProjector projector,
            ElasticsearchGateway elasticsearch,
            DlqStore productDlq,
            RecordDlqStore recordDlq,
            FailpointRegistry failpoints,
            @Value("${pipeline.target-alias:products_write}") String targetAlias,
            @Value("${pipeline.retry-attempts:3}") int retryAttempts) {
        if (retryAttempts < 1) {
            throw new IllegalArgumentException("retryAttempts must be positive");
        }
        this.parser = parser;
        this.source = source;
        this.projector = projector;
        this.elasticsearch = elasticsearch;
        this.productDlq = productDlq;
        this.recordDlq = recordDlq;
        this.failpoints = failpoints;
        this.targetAlias = targetAlias;
        this.retryAttempts = retryAttempts;
    }

    public ProcessingResult process(ConsumerRecord<String, String> record) {
        List<RevisionSignal> parsed = parseOrDlq(record);
        if (parsed == null) {
            return new ProcessingResult(0, 0, 0, 0, 1, 0);
        }
        List<RevisionSignal> signals = deduplicate(parsed);
        if (signals.isEmpty()) {
            return new ProcessingResult(0, 0, 0, 0, 0, 0);
        }

        List<SearchDocument> documents = new ArrayList<>();
        int productDlqCount = 0;
        long highestRevision = 0;
        for (RevisionSignal signal : signals) {
            Optional<SourceProductSnapshot> loaded = source.load(signal.productId());
            if (loaded.isEmpty()) {
                publishProductDlq(record, signal.productId(), signal.eventRevision(),
                        minimalPayload(signal.productId(), signal.eventRevision()),
                        "MISSING_SOURCE", "source row is missing");
                productDlqCount++;
                continue;
            }
            SourceProductSnapshot snapshot = loaded.get();
            if (snapshot.revision() < signal.eventRevision()) {
                throw new RetryablePipelineException(
                        "source revision " + snapshot.revision() + " is behind event revision "
                                + signal.eventRevision() + " for product " + signal.productId());
            }
            documents.add(projector.project(snapshot));
            highestRevision = Math.max(highestRevision, snapshot.revision());
        }

        Settlement settlement = writeWithRetries(documents);
        for (BulkItemResult item : settlement.permanent()) {
            SearchDocument document = documentFor(documents, item.productId(), item.revision());
            publishProductDlq(record, item.productId(), item.revision(), serialize(document),
                    item.errorType() == null ? "PERMANENT_FAILURE" : item.errorType(),
                    item.reason() == null ? "permanent Elasticsearch item failure" : item.reason());
            productDlqCount++;
        }
        return new ProcessingResult(signals.size(), settlement.applied(), settlement.stale(),
                productDlqCount, 0, highestRevision);
    }

    private List<RevisionSignal> parseOrDlq(ConsumerRecord<String, String> record) {
        IllegalArgumentException failure = null;
        for (int attempt = 0; attempt < PARSE_ATTEMPTS; attempt++) {
            try {
                return parser.parse(record.value());
            } catch (IllegalArgumentException exception) {
                failure = exception;
            }
        }
        recordDlq.publish(RecordDlqRecord.newPending(recordId(record), record.topic(),
                record.partition(), record.offset(), record.key(), record.value(),
                failure.getClass().getSimpleName(), message(failure)));
        failpoints.hit(Failpoint.AFTER_DLQ_PUBLISH);
        return null;
    }

    private static List<RevisionSignal> deduplicate(List<RevisionSignal> parsed) {
        Map<Long, RevisionSignal> byProduct = new LinkedHashMap<>();
        for (RevisionSignal signal : parsed) {
            byProduct.merge(signal.productId(), signal, (left, right) ->
                    right.eventRevision() > left.eventRevision() ? right : left);
        }
        return byProduct.values().stream()
                .sorted(Comparator.comparingLong(RevisionSignal::productId))
                .toList();
    }

    private Settlement writeWithRetries(List<SearchDocument> documents) {
        List<SearchDocument> pending = List.copyOf(documents);
        int applied = 0;
        int stale = 0;
        List<BulkItemResult> permanent = new ArrayList<>();
        for (int attempt = 1; !pending.isEmpty() && attempt <= retryAttempts; attempt++) {
            BulkWriteResult result;
            try {
                result = elasticsearch.write(targetAlias, pending);
            } catch (BulkTransportException | BulkProtocolException exception) {
                if (attempt == retryAttempts) {
                    throw new RetryablePipelineException("Elasticsearch Bulk attempts exhausted", exception);
                }
                continue;
            }
            Map<String, SearchDocument> requested = new LinkedHashMap<>();
            for (SearchDocument document : pending) {
                requested.put(identity(document.productId(), document.sourceRevision()), document);
            }
            List<SearchDocument> retry = new ArrayList<>();
            for (BulkItemResult item : result.items()) {
                SearchDocument document = requested.remove(identity(item.productId(), item.revision()));
                if (document == null) {
                    throw new RetryablePipelineException("Bulk response contains an unexpected item identity");
                }
                if (item.outcome() == BulkOutcome.APPLIED) {
                    applied++;
                } else if (item.outcome() == BulkOutcome.STALE) {
                    stale++;
                } else if (item.outcome() == BulkOutcome.PERMANENT_FAILURE) {
                    permanent.add(item);
                } else {
                    retry.add(document);
                }
            }
            if (!requested.isEmpty()) {
                throw new RetryablePipelineException("Bulk response omitted requested item identities");
            }
            pending = List.copyOf(retry);
        }
        if (!pending.isEmpty()) {
            throw new RetryablePipelineException("retryable Elasticsearch items exhausted attempts");
        }
        return new Settlement(applied, stale, List.copyOf(permanent));
    }

    private void publishProductDlq(
            ConsumerRecord<String, String> record, long productId, long revision,
            String payload, String failureClass, String error) {
        productDlq.publish(DlqRecord.newPending(recordId(record) + ':' + productId,
                record.topic(), record.partition(), record.offset(), productId, revision,
                payload, failureClass, error));
        failpoints.hit(Failpoint.AFTER_DLQ_PUBLISH);
    }

    private String serialize(SearchDocument document) {
        try {
            return json.writeValueAsString(document);
        } catch (JacksonException exception) {
            throw new IllegalArgumentException("cannot serialize product DLQ payload", exception);
        }
    }

    private static String minimalPayload(long productId, long revision) {
        return "{\"product_id\":" + productId + ",\"source_revision\":" + revision + "}";
    }

    private static SearchDocument documentFor(List<SearchDocument> documents, long productId, long revision) {
        return documents.stream()
                .filter(document -> document.productId() == productId
                        && document.sourceRevision() == revision)
                .findFirst()
                .orElseThrow(() -> new RetryablePipelineException(
                        "permanent Bulk item has no matching requested document"));
    }

    private static String identity(long productId, long revision) {
        return productId + ":" + revision;
    }

    private static String recordId(ConsumerRecord<String, String> record) {
        return record.topic() + ':' + record.partition() + ':' + record.offset();
    }

    private static String message(Throwable failure) {
        return failure.getMessage() == null ? failure.getClass().getSimpleName() : failure.getMessage();
    }

    private record Settlement(int applied, int stale, List<BulkItemResult> permanent) {
    }
}
