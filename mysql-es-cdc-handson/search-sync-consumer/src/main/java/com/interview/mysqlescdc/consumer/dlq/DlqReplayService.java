package com.interview.mysqlescdc.consumer.dlq;

import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import com.interview.mysqlescdc.consumer.projection.*;
import com.interview.mysqlescdc.consumer.sink.*;
import com.interview.mysqlescdc.consumer.source.*;

@Service
public class DlqReplayService {
    private final DlqStore store;
    private final SourceSnapshotRepository source;
    private final SearchDocumentProjector projector;
    private final ElasticsearchGateway elasticsearch;
    private final String targetAlias;

    public DlqReplayService(DlqStore store, SourceSnapshotRepository source,
            SearchDocumentProjector projector, ElasticsearchGateway elasticsearch,
            @Value("${pipeline.target-alias:products_write}") String targetAlias) {
        this.store = store; this.source = source; this.projector = projector;
        this.elasticsearch = elasticsearch; this.targetAlias = targetAlias;
    }

    public ReplayResult replay(String eventId) {
        var found = store.findPending(eventId);
        if (found.isEmpty()) return ReplayResult.notFound(eventId);
        DlqRecord pending = found.get();
        var snapshot = source.load(pending.productId());
        if (snapshot.isEmpty()) return remain(pending, null, null);
        SearchDocument document;
        try { document = projector.project(snapshot.get()); }
        catch (RuntimeException failure) { return remain(pending, snapshot.get().revision(), null); }
        BulkItemResult item;
        try {
            BulkWriteResult result = elasticsearch.write(targetAlias, List.of(document));
            if (result.items().size() != 1) return remain(pending, document.sourceRevision(), null);
            item = result.items().getFirst();
            if (item.productId() != document.productId() || item.revision() != document.sourceRevision())
                return remain(pending, document.sourceRevision(), null);
        } catch (RuntimeException failure) {
            return remain(pending, document.sourceRevision(), null);
        }
        boolean settled = item.outcome() == BulkOutcome.APPLIED || item.outcome() == BulkOutcome.STALE;
        if (settled) resolveOrRemain(pending); else republish(pending);
        return new ReplayResult(eventId, pending.sourceRevision(), document.sourceRevision(),
                item.outcome(), settled, settled ? ReplayStatus.RESOLVED : ReplayStatus.PENDING);
    }

    private ReplayResult remain(DlqRecord pending, Long current, BulkOutcome outcome) {
        republish(pending);
        return new ReplayResult(pending.eventId(), pending.sourceRevision(), current, outcome, false, ReplayStatus.PENDING);
    }
    private void republish(DlqRecord r) {
        store.publish(DlqRecord.newPending(r.eventId(), r.topic(), r.partition(), r.offset(),
                r.productId(), r.sourceRevision(), r.payload(), r.failureClass(), r.lastError()));
    }
    private void resolveOrRemain(DlqRecord pending) {
        try {
            store.resolve(pending.eventId());
        } catch (RuntimeException resolveFailure) {
            try {
                republish(pending);
            } catch (RuntimeException republishFailure) {
                republishFailure.addSuppressed(resolveFailure);
                throw republishFailure;
            }
            throw resolveFailure;
        }
    }
}
