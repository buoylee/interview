package com.interview.mysqlescdc.consumer.dlq;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.Test;

import com.interview.mysqlescdc.consumer.projection.SearchDocument;
import com.interview.mysqlescdc.consumer.projection.SearchDocumentProjector;
import com.interview.mysqlescdc.consumer.sink.*;
import com.interview.mysqlescdc.consumer.source.*;

class DlqReplayServiceTest {
    private final DlqStore store = mock(DlqStore.class);
    private final SourceSnapshotRepository source = mock(SourceSnapshotRepository.class);
    private final SearchDocumentProjector projector = new SearchDocumentProjector();
    private final ElasticsearchGateway gateway = mock(ElasticsearchGateway.class);
    private final DlqReplayService service = new DlqReplayService(store, source, projector, gateway, "products_write");

    @Test void missing_event_is_not_found_without_side_effects() {
        when(store.findPending("missing")).thenReturn(Optional.empty());
        assertThat(service.replay("missing").status()).isEqualTo(ReplayStatus.NOT_FOUND);
        verifyNoInteractions(source, gateway);
    }

    @Test void replay_reloads_current_source_and_resolves_only_after_applied() {
        DlqRecord pending = pending("t:0:1:7", 7, 1);
        SourceProductSnapshot current = active(7, 4);
        when(store.findPending("t:0:1:7")).thenReturn(Optional.of(pending));
        when(source.load(7)).thenReturn(Optional.of(current));
        when(gateway.write(eq("products_write"), anyList())).thenReturn(new BulkWriteResult(List.of(
                new BulkItemResult(7, 4, BulkOutcome.APPLIED, 201, null, null))));

        ReplayResult result = service.replay("t:0:1:7");

        assertThat(result).isEqualTo(new ReplayResult("t:0:1:7", 1L, 4L, BulkOutcome.APPLIED, true, ReplayStatus.RESOLVED));
        verify(store).resolve("t:0:1:7");
        verify(gateway).write(eq("products_write"), argThat(documents ->
                documents.size() == 1 && documents.getFirst().sourceRevision() == 4));
    }

    @Test void stale_is_settled_but_retryable_and_permanent_remain_pending() {
        DlqRecord pending = pending("t:0:1:7", 7, 1);
        when(store.findPending("t:0:1:7")).thenReturn(Optional.of(pending));
        when(source.load(7)).thenReturn(Optional.of(active(7, 4)));
        when(gateway.write(anyString(), anyList()))
                .thenReturn(result(BulkOutcome.STALE))
                .thenReturn(result(BulkOutcome.RETRYABLE_FAILURE))
                .thenReturn(result(BulkOutcome.PERMANENT_FAILURE));

        assertThat(service.replay("t:0:1:7").resolved()).isTrue();
        assertThat(service.replay("t:0:1:7").status()).isEqualTo(ReplayStatus.PENDING);
        assertThat(service.replay("t:0:1:7").status()).isEqualTo(ReplayStatus.PENDING);
        verify(store, times(1)).resolve("t:0:1:7");
        verify(store, times(2)).publish(any());
    }

    @Test void missing_current_source_stays_pending_and_never_writes_stored_payload() {
        when(store.findPending("t:0:1:7")).thenReturn(Optional.of(pending("t:0:1:7", 7, 1)));
        when(source.load(7)).thenReturn(Optional.empty());
        assertThat(service.replay("t:0:1:7").status()).isEqualTo(ReplayStatus.PENDING);
        verifyNoInteractions(gateway);
        verify(store).publish(any());
        verify(store, never()).resolve(anyString());
    }

    @Test void unexpected_gateway_failure_republishes_exact_immutable_evidence() {
        DlqRecord pending = pending("t:0:1:7", 7, 1);
        when(store.findPending(pending.eventId())).thenReturn(Optional.of(pending));
        when(source.load(7)).thenReturn(Optional.of(active(7, 4)));
        when(gateway.write(anyString(), anyList())).thenThrow(new IllegalStateException("gateway unavailable"));

        assertThat(service.replay(pending.eventId()).status()).isEqualTo(ReplayStatus.PENDING);
        verify(store).publish(argThat(republished ->
                republished.eventId().equals(pending.eventId())
                        && republished.topic().equals(pending.topic())
                        && republished.partition() == pending.partition()
                        && republished.offset() == pending.offset()
                        && republished.productId() == pending.productId()
                        && republished.sourceRevision() == pending.sourceRevision()
                        && republished.payload().equals(pending.payload())
                        && republished.failureClass().equals(pending.failureClass())
                        && republished.lastError().equals(pending.lastError())));
        verify(store, never()).resolve(anyString());
    }

    @Test void resolve_failure_republishes_evidence_and_never_reports_resolved() {
        DlqRecord pending = pending("t:0:1:7", 7, 1);
        when(store.findPending(pending.eventId())).thenReturn(Optional.of(pending));
        when(source.load(7)).thenReturn(Optional.of(active(7, 4)));
        when(gateway.write(anyString(), anyList())).thenReturn(result(BulkOutcome.APPLIED));
        doThrow(new IllegalStateException("resolve failed")).when(store).resolve(pending.eventId());

        assertThatThrownBy(() -> service.replay(pending.eventId()))
                .isInstanceOf(IllegalStateException.class).hasMessage("resolve failed");
        verify(store).publish(argThat(republished -> sameEvidence(pending, republished)));
    }

    @Test void republish_failure_propagates_without_claiming_an_attempt_or_resolution() {
        DlqRecord pending = pending("t:0:1:7", 7, 1);
        when(store.findPending(pending.eventId())).thenReturn(Optional.of(pending));
        when(source.load(7)).thenReturn(Optional.empty());
        doThrow(new IllegalStateException("publish failed")).when(store).publish(any());

        assertThatThrownBy(() -> service.replay(pending.eventId()))
                .isInstanceOf(IllegalStateException.class).hasMessage("publish failed");
        verify(store, never()).resolve(anyString());
    }

    @Test void republish_failure_after_resolve_failure_is_primary_and_retains_resolve_as_suppressed() {
        DlqRecord pending = pending("t:0:1:7", 7, 1);
        when(store.findPending(pending.eventId())).thenReturn(Optional.of(pending));
        when(source.load(7)).thenReturn(Optional.of(active(7, 4)));
        when(gateway.write(anyString(), anyList())).thenReturn(result(BulkOutcome.STALE));
        doThrow(new IllegalStateException("resolve failed")).when(store).resolve(pending.eventId());
        doThrow(new IllegalArgumentException("publish failed")).when(store).publish(any());

        assertThatThrownBy(() -> service.replay(pending.eventId()))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("publish failed")
                .satisfies(failure -> assertThat(failure.getSuppressed()).singleElement()
                        .isInstanceOfSatisfying(IllegalStateException.class,
                                suppressed -> assertThat(suppressed).hasMessage("resolve failed")));
    }

    private BulkWriteResult result(BulkOutcome outcome) {
        return new BulkWriteResult(List.of(new BulkItemResult(7, 4, outcome, 400, "x", "reason")));
    }
    private DlqRecord pending(String id, long product, long revision) {
        return DlqRecord.newPending(id, "t", 0, 1, product, revision,
                "{\"product_id\":" + product + ",\"source_revision\":" + revision + "}", "X", "old");
    }
    private boolean sameEvidence(DlqRecord expected, DlqRecord actual) {
        return actual.isNewPending() && actual.eventId().equals(expected.eventId())
                && actual.topic().equals(expected.topic()) && actual.partition()==expected.partition()
                && actual.offset()==expected.offset() && actual.productId()==expected.productId()
                && actual.sourceRevision()==expected.sourceRevision() && actual.payload().equals(expected.payload())
                && actual.failureClass().equals(expected.failureClass()) && actual.lastError().equals(expected.lastError());
    }
    private SourceProductSnapshot active(long id, long revision) {
        return new SourceProductSnapshot(id, "sku", "name", "description", 2L, "cat", 100L, 3,
                true, revision, java.time.Instant.parse("2026-01-01T00:00:00Z"));
    }
}
