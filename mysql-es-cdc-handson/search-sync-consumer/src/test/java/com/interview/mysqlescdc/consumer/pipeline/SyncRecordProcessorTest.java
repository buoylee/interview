package com.interview.mysqlescdc.consumer.pipeline;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import com.interview.mysqlescdc.consumer.canal.CanalRevisionParser;
import com.interview.mysqlescdc.consumer.canal.RevisionSignal;
import com.interview.mysqlescdc.consumer.dlq.DlqRecord;
import com.interview.mysqlescdc.consumer.dlq.DlqStore;
import com.interview.mysqlescdc.consumer.dlq.RecordDlqRecord;
import com.interview.mysqlescdc.consumer.dlq.RecordDlqStore;
import com.interview.mysqlescdc.consumer.failpoint.Failpoint;
import com.interview.mysqlescdc.consumer.failpoint.FailpointRegistry;
import com.interview.mysqlescdc.consumer.projection.SearchDocumentProjector;
import com.interview.mysqlescdc.consumer.projection.SearchDocument;
import com.interview.mysqlescdc.consumer.sink.BulkItemResult;
import com.interview.mysqlescdc.consumer.sink.BulkOutcome;
import com.interview.mysqlescdc.consumer.sink.BulkTransportException;
import com.interview.mysqlescdc.consumer.sink.BulkWriteResult;
import com.interview.mysqlescdc.consumer.sink.ElasticsearchGateway;
import com.interview.mysqlescdc.consumer.source.SourceProductSnapshot;
import com.interview.mysqlescdc.consumer.source.SourceSnapshotRepository;
import tools.jackson.databind.json.JsonMapper;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import com.interview.mysqlescdc.consumer.metrics.PipelineMetrics;

class SyncRecordProcessorTest {
    private final SourceSnapshotRepository source = mock(SourceSnapshotRepository.class);
    private final ElasticsearchGateway elasticsearch = mock(ElasticsearchGateway.class);
    private final DlqStore productDlq = mock(DlqStore.class);
    private final RecordDlqStore recordDlq = mock(RecordDlqStore.class);
    private final FailpointRegistry failpoints = mock(FailpointRegistry.class);
    private final SyncRecordProcessor processor = new SyncRecordProcessor(
            new CanalRevisionParser(JsonMapper.builder().build()), source,
            new SearchDocumentProjector(), elasticsearch, productDlq, recordDlq,
            failpoints, "products_write", 3);

    @Test
    void records_low_cardinality_runtime_metrics_from_real_processing_outcomes() {
        var registry = new SimpleMeterRegistry();
        processor.configureMetrics(new PipelineMetrics(registry, () -> 0L, () -> 0L));
        when(source.load(7)).thenReturn(Optional.of(snapshot(7, 4)));
        when(elasticsearch.write(eq("products_write"), any())).thenReturn(new BulkWriteResult(List.of(
                item(7, 4, BulkOutcome.STALE, 409, "version_conflict_engine_exception"))));
        processor.process(record(message(row(7, 4, true))));
        assertThat(registry.get("cdc_consumer_records_total").counter().count()).isEqualTo(1);
        assertThat(registry.get("cdc_consumer_signals_total").counter().count()).isEqualTo(1);
        assertThat(registry.get("cdc_es_bulk_items_total").tag("outcome", "stale").counter().count()).isEqualTo(1);
        assertThat(registry.get("cdc_stale_revision_total").counter().count()).isEqualTo(1);
        assertThat(registry.get("cdc_last_success_epoch_seconds").gauge().value()).isPositive();
    }

    @Test
    void deduplicates_by_highest_revision_and_settles_applied_and_stale_items() {
        when(source.load(7)).thenReturn(Optional.of(snapshot(7, 4)));
        when(source.load(8)).thenReturn(Optional.of(snapshot(8, 2)));
        when(elasticsearch.write(eq("products_write"), any())).thenReturn(new BulkWriteResult(List.of(
                item(7, 4, BulkOutcome.APPLIED, 201, null),
                item(8, 2, BulkOutcome.STALE, 409, "version_conflict_engine_exception"))));

        ProcessingResult result = processor.process(record(message(
                row(7, 3, false) + "," + row(7, 4, true) + "," + row(8, 2, true))));

        assertThat(result).isEqualTo(new ProcessingResult(2, 1, 1, 0, 0, 4));
        verify(source, times(1)).load(7);
        verify(productDlq, never()).publish(any());
    }

    @Test
    void retries_only_retryable_bulk_items_and_keeps_prior_settlements() {
        when(source.load(7)).thenReturn(Optional.of(snapshot(7, 4)));
        when(source.load(8)).thenReturn(Optional.of(snapshot(8, 2)));
        when(elasticsearch.write(eq("products_write"), any()))
                .thenReturn(new BulkWriteResult(List.of(
                        item(7, 4, BulkOutcome.APPLIED, 201, null),
                        item(8, 2, BulkOutcome.RETRYABLE_FAILURE, 429, "too_many_requests"))))
                .thenReturn(new BulkWriteResult(List.of(
                        item(8, 2, BulkOutcome.APPLIED, 200, null))));

        ProcessingResult result = processor.process(record(message(
                row(7, 4, true) + "," + row(8, 2, true))));

        assertThat(result.appliedCount()).isEqualTo(2);
        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<SearchDocument>> batches = ArgumentCaptor.forClass(List.class);
        verify(elasticsearch, times(2)).write(eq("products_write"), batches.capture());
        assertThat(batches.getAllValues()).extracting(List::size).containsExactly(2, 1);
    }

    @Test
    void rejects_out_of_order_bulk_response_without_retry_dlq_or_settlement() {
        when(source.load(7)).thenReturn(Optional.of(snapshot(7, 4)));
        when(source.load(8)).thenReturn(Optional.of(snapshot(8, 2)));
        when(elasticsearch.write(eq("products_write"), any())).thenReturn(new BulkWriteResult(List.of(
                item(8, 2, BulkOutcome.APPLIED, 201, null),
                item(7, 4, BulkOutcome.APPLIED, 201, null))));

        assertThatThrownBy(() -> processor.process(record(message(
                row(7, 4, true) + "," + row(8, 2, true)))))
                .isInstanceOf(RetryablePipelineException.class);
        verify(elasticsearch, times(1)).write(eq("products_write"), any());
        verify(productDlq, never()).publish(any());
    }

    @Test
    void rejects_duplicate_missing_and_extra_bulk_item_identities_once() {
        assertProtocolViolation(List.of(
                item(7, 4, BulkOutcome.APPLIED, 201, null),
                item(7, 4, BulkOutcome.APPLIED, 201, null)));
        assertProtocolViolation(List.of(item(7, 4, BulkOutcome.APPLIED, 201, null)));
        assertProtocolViolation(List.of(
                item(7, 4, BulkOutcome.APPLIED, 201, null),
                item(8, 2, BulkOutcome.APPLIED, 201, null),
                item(9, 1, BulkOutcome.APPLIED, 201, null)));
    }

    @Test
    void equal_revision_tie_keeps_first_signal_in_original_row_order() {
        RevisionSignal first = new RevisionSignal(7, 4, false, 55, 0);
        RevisionSignal second = new RevisionSignal(7, 4, true, 55, 9);

        List<RevisionSignal> selected = SyncRecordProcessor.deduplicate(List.of(first, second));

        assertThat(selected).containsExactly(first);
    }

    @Test
    void exhausted_retryable_failure_never_becomes_dlq() {
        when(source.load(7)).thenReturn(Optional.of(snapshot(7, 4)));
        when(elasticsearch.write(eq("products_write"), any())).thenReturn(new BulkWriteResult(List.of(
                item(7, 4, BulkOutcome.RETRYABLE_FAILURE, 503, "unavailable"))));

        assertThatThrownBy(() -> processor.process(record(message(row(7, 4, true)))))
                .isInstanceOf(RetryablePipelineException.class);
        verify(elasticsearch, times(3)).write(eq("products_write"), any());
        verify(productDlq, never()).publish(any());
    }

    @Test
    void transport_failure_is_bounded_and_never_ack_settled() {
        when(source.load(7)).thenReturn(Optional.of(snapshot(7, 4)));
        when(elasticsearch.write(eq("products_write"), any()))
                .thenThrow(new BulkTransportException("down"));
        assertThatThrownBy(() -> processor.process(record(message(row(7, 4, true)))))
                .isInstanceOf(RetryablePipelineException.class);
        verify(elasticsearch, times(3)).write(eq("products_write"), any());
    }

    @Test
    void missing_source_and_permanent_bulk_item_are_durable_before_settlement() {
        when(source.load(7)).thenReturn(Optional.empty());
        ProcessingResult missing = processor.process(record(message(row(7, 4, true))));
        assertThat(missing.productDlqCount()).isEqualTo(1);
        assertThat(missing.highestSourceRevision()).isZero();

        when(source.load(8)).thenReturn(Optional.of(snapshot(8, 2)));
        when(elasticsearch.write(eq("products_write"), any())).thenReturn(new BulkWriteResult(List.of(
                item(8, 2, BulkOutcome.PERMANENT_FAILURE, 409, "mapper_parsing_exception"))));
        ProcessingResult permanent = processor.process(record(message(row(8, 2, true))));
        assertThat(permanent.productDlqCount()).isEqualTo(1);
        ArgumentCaptor<DlqRecord> captor = ArgumentCaptor.forClass(DlqRecord.class);
        verify(productDlq, times(2)).publish(captor.capture());
        assertThat(captor.getAllValues()).extracting(DlqRecord::eventId)
                .containsExactly("revisions:1:9:7", "revisions:1:9:8");
        verify(failpoints, times(2)).hit(Failpoint.AFTER_DLQ_PUBLISH);
    }

    @Test
    void source_behind_event_is_retryable_and_never_projected_or_dlqd() {
        when(source.load(7)).thenReturn(Optional.of(snapshot(7, 3)));
        assertThatThrownBy(() -> processor.process(record(message(row(7, 4, true)))))
                .isInstanceOf(RetryablePipelineException.class);
        verify(elasticsearch, never()).write(any(), any());
        verify(productDlq, never()).publish(any());
    }

    @Test
    void poison_is_attempted_exactly_three_times_then_raw_record_is_durable() {
        CountingParser countingParser = new CountingParser();
        SyncRecordProcessor countingProcessor = processorWith(countingParser);
        ConsumerRecord<String, String> poison = new ConsumerRecord<>("revisions", 1, 9, "raw-key", "not-json");
        ProcessingResult result = countingProcessor.process(poison);
        assertThat(result.recordDlqCount()).isEqualTo(1);
        assertThat(countingParser.attempts).isEqualTo(3);
        ArgumentCaptor<RecordDlqRecord> captor = ArgumentCaptor.forClass(RecordDlqRecord.class);
        verify(recordDlq).publish(captor.capture());
        assertThat(captor.getValue().recordId()).isEqualTo("revisions:1:9");
        assertThat(captor.getValue().rawKey()).isEqualTo("raw-key");
        assertThat(captor.getValue().rawPayload()).isEqualTo("not-json");
        verify(failpoints).hit(Failpoint.AFTER_DLQ_PUBLISH);
    }

    @Test
    void either_dlq_publication_failure_propagates_without_after_publish_checkpoint() {
        org.mockito.Mockito.doThrow(new IllegalStateException("db down"))
                .when(recordDlq).publish(any());
        assertThatThrownBy(() -> processor.process(record("not-json")))
                .isInstanceOf(IllegalStateException.class);
        verify(failpoints, never()).hit(Failpoint.AFTER_DLQ_PUBLISH);
    }

    @Test
    void product_dlq_publication_failure_is_not_settled() {
        when(source.load(7)).thenReturn(Optional.empty());
        org.mockito.Mockito.doThrow(new IllegalStateException("db down"))
                .when(productDlq).publish(any());
        assertThatThrownBy(() -> processor.process(record(message(row(7, 4, true)))))
                .isInstanceOf(IllegalStateException.class);
        verify(failpoints, never()).hit(Failpoint.AFTER_DLQ_PUBLISH);
    }

    private static ConsumerRecord<String, String> record(String value) {
        return new ConsumerRecord<>("revisions", 1, 9, "key", value);
    }

    private SyncRecordProcessor processorWith(CanalRevisionParser selectedParser) {
        return new SyncRecordProcessor(selectedParser, source, new SearchDocumentProjector(),
                elasticsearch, productDlq, recordDlq, failpoints, "products_write", 3);
    }

    private void assertProtocolViolation(List<BulkItemResult> responseItems) {
        org.mockito.Mockito.reset(source, elasticsearch, productDlq);
        when(source.load(7)).thenReturn(Optional.of(snapshot(7, 4)));
        when(source.load(8)).thenReturn(Optional.of(snapshot(8, 2)));
        when(elasticsearch.write(eq("products_write"), any()))
                .thenReturn(new BulkWriteResult(responseItems));

        assertThatThrownBy(() -> processor.process(record(message(
                row(7, 4, true) + "," + row(8, 2, true)))))
                .isInstanceOf(RetryablePipelineException.class);
        verify(elasticsearch, times(1)).write(eq("products_write"), any());
        verify(productDlq, never()).publish(any());
    }

    private static final class CountingParser extends CanalRevisionParser {
        private int attempts;

        private CountingParser() {
            super(JsonMapper.builder().build());
        }

        @Override
        public List<RevisionSignal> parse(String payload) {
            attempts++;
            return super.parse(payload);
        }
    }

    private static SourceProductSnapshot snapshot(long id, long revision) {
        return SourceProductSnapshot.active(id, "sku-" + id, "name", "desc", 1,
                "category", 100, 2, revision, Instant.parse("2026-01-01T00:00:00Z"));
    }

    private static BulkItemResult item(long id, long revision, BulkOutcome outcome, int status, String type) {
        return new BulkItemResult(id, revision, outcome, status, type, type == null ? "ok" : type);
    }

    private static String message(String rows) {
        return "{\"id\":55,\"database\":\"product_catalog\",\"table\":\"product_search_revision\","
                + "\"isDdl\":false,\"data\":[" + rows + "]}";
    }

    private static String row(long id, long revision, boolean active) {
        return "{\"product_id\":\"" + id + "\",\"revision\":\"" + revision
                + "\",\"active\":\"" + (active ? "1" : "0") + "\"}";
    }
}
