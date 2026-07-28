package com.interview.mysqlescdc.consumer.dlq;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

import com.interview.mysqlescdc.consumer.canal.CanalRevisionParser;
import com.interview.mysqlescdc.consumer.projection.SearchDocumentProjector;
import com.interview.mysqlescdc.consumer.sink.*;
import com.interview.mysqlescdc.consumer.source.*;

class RecordDlqReplayServiceTest {
    private final RecordDlqStore store = mock(RecordDlqStore.class);
    private final SourceSnapshotRepository source = mock(SourceSnapshotRepository.class);
    private final ElasticsearchGateway gateway = mock(ElasticsearchGateway.class);
    private final RecordDlqReplayService service = new RecordDlqReplayService(store,
            new CanalRevisionParser(JsonMapper.builder().build()), source,
            new SearchDocumentProjector(), gateway, "products_write");

    @Test void malformed_raw_value_remains_pending_and_increments_attempts() {
        when(store.findPending("t:0:1")).thenReturn(Optional.of(pending("not-json")));
        assertThat(service.replay("t:0:1").status()).isEqualTo(ReplayStatus.PENDING);
        verify(store).publish(any());
        verify(store, never()).resolve(anyString());
        verifyNoInteractions(source, gateway);
    }

    @Test void reparses_original_raw_value_rehydrates_each_unique_product_and_resolves_after_all_settle() {
        when(store.findPending("t:0:1")).thenReturn(Optional.of(pending(payload())));
        when(source.load(7)).thenReturn(Optional.of(active(7, 4)));
        when(source.load(8)).thenReturn(Optional.of(active(8, 5)));
        when(gateway.write(eq("products_write"), anyList())).thenReturn(new BulkWriteResult(List.of(
                new BulkItemResult(7, 4, BulkOutcome.APPLIED, 201, null, null),
                new BulkItemResult(8, 5, BulkOutcome.STALE, 409, null, null))));

        RecordReplayResult result = service.replay("t:0:1");

        assertThat(result.resolved()).isTrue();
        assertThat(result.productOutcomes()).containsExactly(BulkOutcome.APPLIED, BulkOutcome.STALE);
        verify(source).load(7);
        verify(source).load(8);
        verify(store).resolve("t:0:1");
    }

    @Test void any_unsettled_product_keeps_whole_record_pending() {
        when(store.findPending("t:0:1")).thenReturn(Optional.of(pending(payload())));
        when(source.load(7)).thenReturn(Optional.of(active(7, 4)));
        when(source.load(8)).thenReturn(Optional.empty());
        assertThat(service.replay("t:0:1").resolved()).isFalse();
        verify(store).publish(any());
        verify(store, never()).resolve(anyString());
        verifyNoInteractions(gateway);
    }

    @Test void unexpected_gateway_runtime_republishes_exact_evidence_and_stays_pending() {
        RecordDlqRecord pending = pending(payload());
        when(store.findPending(pending.recordId())).thenReturn(Optional.of(pending));
        when(source.load(7)).thenReturn(Optional.of(active(7, 4)));
        when(source.load(8)).thenReturn(Optional.of(active(8, 5)));
        when(gateway.write(anyString(), anyList())).thenThrow(new IllegalStateException("gateway failed"));

        assertThat(service.replay(pending.recordId()).status()).isEqualTo(ReplayStatus.PENDING);
        verify(store).publish(argThat(republished -> sameEvidence(pending, republished)));
        verify(store, never()).resolve(anyString());
    }

    @Test void resolve_failure_republishes_exact_evidence_and_never_reports_resolved() {
        RecordDlqRecord pending = pending(payload());
        when(store.findPending(pending.recordId())).thenReturn(Optional.of(pending));
        when(source.load(7)).thenReturn(Optional.of(active(7, 4)));
        when(source.load(8)).thenReturn(Optional.of(active(8, 5)));
        when(gateway.write(anyString(), anyList())).thenReturn(new BulkWriteResult(List.of(
                new BulkItemResult(7,4,BulkOutcome.APPLIED,201,null,null),
                new BulkItemResult(8,5,BulkOutcome.STALE,409,null,null))));
        doThrow(new IllegalStateException("resolve failed")).when(store).resolve(pending.recordId());

        assertThatThrownBy(() -> service.replay(pending.recordId()))
                .isInstanceOf(IllegalStateException.class).hasMessage("resolve failed");
        verify(store).publish(argThat(republished -> sameEvidence(pending, republished)));
    }

    @Test void republish_failure_propagates_and_does_not_claim_resolution() {
        RecordDlqRecord pending = pending("not-json");
        when(store.findPending(pending.recordId())).thenReturn(Optional.of(pending));
        doThrow(new IllegalStateException("publish failed")).when(store).publish(any());

        assertThatThrownBy(() -> service.replay(pending.recordId()))
                .isInstanceOf(IllegalStateException.class).hasMessage("publish failed");
        verify(store, never()).resolve(anyString());
    }

    @Test void republish_failure_after_resolve_failure_is_primary_and_suppresses_resolve_failure() {
        RecordDlqRecord pending = pending(payload());
        when(store.findPending(pending.recordId())).thenReturn(Optional.of(pending));
        when(source.load(7)).thenReturn(Optional.of(active(7, 4)));
        when(source.load(8)).thenReturn(Optional.of(active(8, 5)));
        when(gateway.write(anyString(), anyList())).thenReturn(new BulkWriteResult(List.of(
                new BulkItemResult(7,4,BulkOutcome.APPLIED,201,null,null),
                new BulkItemResult(8,5,BulkOutcome.STALE,409,null,null))));
        doThrow(new IllegalStateException("resolve failed")).when(store).resolve(pending.recordId());
        doThrow(new IllegalArgumentException("publish failed")).when(store).publish(any());

        assertThatThrownBy(() -> service.replay(pending.recordId()))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("publish failed")
                .satisfies(failure -> assertThat(failure.getSuppressed()).singleElement()
                        .isInstanceOfSatisfying(IllegalStateException.class,
                                suppressed -> assertThat(suppressed).hasMessage("resolve failed")));
    }

    private RecordDlqRecord pending(String raw) {
        return RecordDlqRecord.newPending("t:0:1", "t", 0, 1, null, raw, "PARSE", "old");
    }
    private boolean sameEvidence(RecordDlqRecord expected, RecordDlqRecord actual) {
        return actual.isNewPending() && actual.recordId().equals(expected.recordId())
                && actual.topic().equals(expected.topic()) && actual.partition()==expected.partition()
                && actual.offset()==expected.offset() && java.util.Objects.equals(actual.rawKey(),expected.rawKey())
                && actual.rawPayload().equals(expected.rawPayload())
                && actual.failureClass().equals(expected.failureClass()) && actual.lastError().equals(expected.lastError());
    }
    private String payload() {
        return "{\"id\":1,\"database\":\"product_catalog\",\"table\":\"product_search_revision\",\"isDdl\":false,\"data\":[{\"product_id\":\"7\",\"revision\":\"2\",\"active\":\"1\"},{\"product_id\":\"8\",\"revision\":\"3\",\"active\":\"1\"},{\"product_id\":\"7\",\"revision\":\"2\",\"active\":\"1\"}]}";
    }
    private SourceProductSnapshot active(long id, long revision) {
        return new SourceProductSnapshot(id, "sku", "name", "description", 2L, "cat", 100L, 3,
                true, revision, java.time.Instant.parse("2026-01-01T00:00:00Z"));
    }
}
