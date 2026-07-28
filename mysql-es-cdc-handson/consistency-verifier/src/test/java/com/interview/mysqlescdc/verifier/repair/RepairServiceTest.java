package com.interview.mysqlescdc.verifier.repair;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

import com.interview.mysqlescdc.verifier.diff.DifferenceType;
import com.interview.mysqlescdc.verifier.diff.DocumentDifference;
import com.interview.mysqlescdc.verifier.run.StoredVerificationRun;
import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;
import com.interview.mysqlescdc.verifier.run.VerificationRunStore;
import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.source.ExpectedDocumentReader;
import com.interview.mysqlescdc.verifier.source.SourceWatermarkReader;
import com.interview.mysqlescdc.verifier.target.IndexedDocument;

class RepairServiceTest {
    private final VerificationRunStore store = mock(VerificationRunStore.class);
    private final SourceWatermarkReader watermark = mock(SourceWatermarkReader.class);
    private final ExpectedDocumentReader source = mock(ExpectedDocumentReader.class);
    private final RepairGateway gateway = mock(RepairGateway.class);
    private final RepairService service = new RepairService(store, watermark, source, gateway, 100);
    private final UUID runId = UUID.fromString("00000000-0000-0000-0000-000000000044");

    @Test
    void only_conclusive_diff_within_limit_and_without_log_gap_is_eligible() {
        for (VerificationRunStatus status : List.of(
                VerificationRunStatus.PASS, VerificationRunStatus.RUNNING,
                VerificationRunStatus.INCONCLUSIVE, VerificationRunStatus.FAILED)) {
            when(store.findRun(runId)).thenReturn(Optional.of(run(status, 1)));
            assertThatThrownBy(() -> service.repair(runId))
                    .hasMessageContaining("conclusive DIFF");
        }
        when(store.findRun(runId)).thenReturn(Optional.of(run(VerificationRunStatus.DIFF, 101)));
        assertThatThrownBy(() -> service.repair(runId)).hasMessageContaining("repair limit");

        when(store.findRun(runId)).thenReturn(Optional.of(run(VerificationRunStatus.DIFF, 1)));
        when(store.conditionActive("LOG_GAP")).thenReturn(true);
        assertThatThrownBy(() -> service.repair(runId)).hasMessageContaining("LOG_GAP");
        verify(gateway, never()).write(any(), any(), any());
    }

    @Test
    void action_mapping_persists_started_before_side_effect_and_uses_current_source() {
        ExpectedDocument currentMissing = active(1, 11);
        ExpectedDocument currentStale = ExpectedDocument.tombstone(2, 12, now());
        ExpectedDocument currentModified = active(3, 13);
        ExpectedDocument currentTombstone = ExpectedDocument.tombstone(4, 14, now());
        List<DocumentDifference> differences = List.of(
                DocumentDifference.missing(active(1, 10)),
                difference(DifferenceType.STALE, active(2, 12), indexed(active(2, 11), 11)),
                difference(DifferenceType.MODIFIED, active(3, 13), indexed(active(3, 13), 13)),
                difference(DifferenceType.TOMBSTONE_MISMATCH,
                        ExpectedDocument.tombstone(4, 14, now()), indexed(active(4, 14), 14)),
                DocumentDifference.extra(indexed(active(5, 15), 15)));
        eligible(differences);
        when(source.load(1)).thenReturn(Optional.of(currentMissing));
        when(source.load(2)).thenReturn(Optional.of(currentStale));
        when(source.load(3)).thenReturn(Optional.of(currentModified));
        when(source.load(4)).thenReturn(Optional.of(currentTombstone));
        when(gateway.write(any(), any(), any())).thenReturn(RepairOutcome.APPLIED);
        when(gateway.deleteExtra(any(), any())).thenReturn(RepairOutcome.APPLIED);

        RepairReport report = service.repair(runId);

        assertThat(report.repaired()).isTrue();
        assertThat(report.applied()).isEqualTo(5);
        verify(gateway).write("products_write", RepairActionType.WRITE_EXTERNAL_GTE, currentMissing);
        verify(gateway).write("products_write", RepairActionType.WRITE_EXTERNAL, currentStale);
        verify(gateway).write("products_write", RepairActionType.WRITE_EXTERNAL_GTE, currentModified);
        verify(gateway).write("products_write", RepairActionType.WRITE_EXTERNAL_GTE, currentTombstone);
        verify(gateway).deleteExtra("products_write", differences.get(4).actual());
        InOrder durableOrder = inOrder(store, gateway);
        durableOrder.verify(store).markActionStarted(any(), eq(runId), eq(1L),
                eq(RepairActionType.WRITE_EXTERNAL_GTE), eq(70L), eq(11L));
        durableOrder.verify(gateway).write(
                "products_write", RepairActionType.WRITE_EXTERNAL_GTE, currentMissing);
    }

    @Test
    void terminal_action_is_backfilled_before_it_is_counted_as_skipped() {
        DocumentDifference missing = DocumentDifference.missing(active(1, 10));
        eligible(List.of(missing));
        when(store.findRepairAction(runId, 1L)).thenReturn(Optional.of(
                new RepairActionRecord(UUID.randomUUID(), 1L,
                        RepairActionType.WRITE_EXTERNAL_GTE, RepairOutcome.APPLIED)));
        when(store.markDifferenceRepaired(runId, 1L, "APPLIED")).thenReturn(true);

        RepairReport report = service.repair(runId);

        assertThat(report.repaired()).isTrue();
        assertThat(report.skipped()).isOne();
        verify(store).markDifferenceRepaired(runId, 1L, "APPLIED");
        verify(store).markRunRepaired(runId);
        verify(gateway, never()).write(any(), any(), any());
    }

    @Test
    void unsafe_revision_differences_activate_rebuild_and_never_write() {
        List<DocumentDifference> differences = List.of(difference(
                DifferenceType.FUTURE_REVISION, active(8, 8), indexed(active(8, 9), 9)));
        when(store.findRun(runId)).thenReturn(Optional.of(run(VerificationRunStatus.DIFF, 1)));
        when(store.loadDifferences(runId, 101)).thenReturn(differences);

        assertThatThrownBy(() -> service.repair(runId)).hasMessageContaining("requires rebuild");

        verify(store).activateCondition(eq("REBUILD_REQUIRED"), any());
        verify(gateway, never()).write(any(), any(), any());
    }

    @Test
    void unsafe_difference_activates_rebuild_before_over_limit_or_log_gap_rejection() {
        when(store.findRun(runId)).thenReturn(Optional.of(run(VerificationRunStatus.DIFF, 101)));
        when(store.hasUnsafeDifferences(runId)).thenReturn(true);
        when(store.conditionActive("LOG_GAP")).thenReturn(true);

        assertThatThrownBy(() -> service.repair(runId)).hasMessageContaining("requires rebuild");

        verify(store).activateCondition(eq("REBUILD_REQUIRED"), any());
        verify(store, never()).loadDifferences(any(), anyInt());
        verify(store, never()).conditionActive("LOG_GAP");
        verify(gateway, never()).write(any(), any(), any());
    }

    @Test
    void unsafe_evidence_does_not_activate_rebuild_for_non_conclusive_runs() {
        for (VerificationRunStatus status : List.of(
                VerificationRunStatus.RUNNING, VerificationRunStatus.INCONCLUSIVE)) {
            when(store.findRun(runId)).thenReturn(Optional.of(run(status, 1)));
            when(store.hasUnsafeDifferences(runId)).thenReturn(true);

            assertThatThrownBy(() -> service.repair(runId))
                    .hasMessageContaining("conclusive DIFF");
        }

        verify(store, never()).hasUnsafeDifferences(runId);
        verify(store, never()).activateCondition(eq("REBUILD_REQUIRED"), any());
    }

    @Test
    void unsafe_evidence_does_not_activate_rebuild_for_moving_diff_run() {
        when(store.findRun(runId)).thenReturn(Optional.of(new StoredVerificationRun(
                runId, "products_write", VerificationRunStatus.DIFF, 50, 51L, 1)));
        when(store.hasUnsafeDifferences(runId)).thenReturn(true);

        assertThatThrownBy(() -> service.repair(runId))
                .hasMessageContaining("unchanged verification watermark");

        verify(store, never()).hasUnsafeDifferences(runId);
        verify(store, never()).activateCondition(eq("REBUILD_REQUIRED"), any());
    }

    @Test
    void extra_is_not_deleted_when_current_source_fact_now_exists() {
        DocumentDifference extra = DocumentDifference.extra(indexed(active(5, 15), 15));
        eligible(List.of(extra));
        when(source.load(5)).thenReturn(Optional.of(active(5, 16)));

        RepairReport report = service.repair(runId);

        assertThat(report.repaired()).isFalse();
        assertThat(report.applied()).isZero();
        verify(source).load(5);
        verify(gateway, never()).deleteExtra(any(), any());
        verify(store, never()).markRunRepaired(runId);
    }

    @Test
    void log_gap_activated_before_side_effect_stops_without_external_write() {
        List<DocumentDifference> differences = List.of(DocumentDifference.missing(active(1, 10)));
        eligible(differences);
        when(source.load(1)).thenReturn(Optional.of(active(1, 10)));
        when(store.conditionActive("LOG_GAP")).thenReturn(false, true);

        RepairReport report = service.repair(runId);

        assertThat(report.repaired()).isFalse();
        verify(gateway, never()).write(any(), any(), any());
        verify(store, never()).markRunRepaired(runId);
    }

    @Test
    void log_gap_activated_after_actions_blocks_final_repaired_transition() {
        List<DocumentDifference> differences = List.of(DocumentDifference.missing(active(1, 10)));
        eligible(differences);
        when(source.load(1)).thenReturn(Optional.of(active(1, 10)));
        when(gateway.write(any(), any(), any())).thenReturn(RepairOutcome.APPLIED);
        when(store.conditionActive("LOG_GAP")).thenReturn(false, false, true);

        RepairReport report = service.repair(runId);

        assertThat(report.applied()).isOne();
        assertThat(report.repaired()).isFalse();
        verify(store).finishAction(any(), eq(RepairOutcome.APPLIED), eq(null));
        verify(store, never()).markRunRepaired(runId);
    }

    @Test
    void moving_repair_watermark_stops_without_marking_run_repaired() {
        List<DocumentDifference> differences = List.of(DocumentDifference.missing(active(1, 10)));
        when(store.findRun(runId)).thenReturn(Optional.of(run(VerificationRunStatus.DIFF, 1)));
        when(store.loadDifferences(runId, 101)).thenReturn(differences);
        when(watermark.current()).thenReturn(80L, 81L, 81L);

        RepairReport report = service.repair(runId);

        assertThat(report.sourceStable()).isFalse();
        assertThat(report.repaired()).isFalse();
        verify(gateway, never()).write(any(), any(), any());
        verify(store, never()).markRunRepaired(runId);
    }

    private void eligible(List<DocumentDifference> differences) {
        when(store.findRun(runId)).thenReturn(Optional.of(
                new StoredVerificationRun(runId, "products_write", VerificationRunStatus.DIFF,
                        60, 60L, differences.size())));
        when(store.loadDifferences(runId, 101)).thenReturn(differences);
        when(store.markDifferenceRepaired(eq(runId), anyLong(), any(String.class)))
                .thenReturn(true);
        when(watermark.current()).thenReturn(70L);
    }

    private StoredVerificationRun run(VerificationRunStatus status, long count) {
        return new StoredVerificationRun(runId, "products_write", status, 50, 50L, count);
    }

    private DocumentDifference difference(
            DifferenceType type, ExpectedDocument expected, IndexedDocument actual) {
        return new DocumentDifference(expected.productId(), type, expected, actual, List.of());
    }

    private ExpectedDocument active(long id, long revision) {
        return new ExpectedDocument(id, "SKU-" + id, "Product " + id, "Description",
                10L, "Category", 1000L + id, 4, true, revision, now());
    }

    private IndexedDocument indexed(ExpectedDocument expected, long version) {
        return IndexedDocument.fromExpected(expected, version, 1, 1);
    }

    private Instant now() {
        return Instant.parse("2026-07-22T03:04:05Z");
    }
}
