package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class CanalRecoveryEvidenceTest {
    @Test void accepts_only_complete_position_restart_and_distinct_sentinel_evidence() {
        valid().validate();
    }

    @Test void rejects_changed_offsets_across_reset_false_restart() {
        var e = valid();
        var invalid = copy(e, Map.of(0, 11L, 1, 20L, 2, 30L));
        assertThatThrownBy(invalid::validate).isInstanceOf(IllegalArgumentException.class);
    }

    @Test void rejects_reset_cursor_before_gate_stable_lower_bound() {
        var e = valid();
        var invalid = new CanalRecoveryEvidence(e.recoveryId(), e.cursorPath(), e.cursorBackupPath(),
                e.oldCursorSha256(), e.oldJournalName(), e.oldPosition(), e.retainedManifest(),
                e.resetLowerBoundJournal(), e.resetLowerBoundFileIndex(), 900,
                e.resetCursorSha256(), e.resetJournalName(), e.resetFileIndex(), 800,
                e.resetAnchorRunId(), e.resetAnchorOffsets(), e.resetAnchorEvents(),
                e.resetRestartOffsetsBefore(), e.normalRestartCursorSha256(),
                e.normalRestartJournalName(), e.normalRestartFileIndex(), e.normalRestartPosition(),
                e.normalRestartOffsetsAfter(), e.normalSentinelRunId(), e.normalSentinelOffsets(),
                e.normalSentinelEvents());
        assertThatThrownBy(invalid::validate).isInstanceOf(IllegalArgumentException.class);
    }

    @Test void normal_sentinels_must_be_strictly_after_the_restart_vector() {
        assertThatThrownBy(evidenceWithNormalSentinels(Map.of(0,10L,1,20L,2,30L))::validate).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(evidenceWithNormalSentinels(Map.of(0,9L,1,21L,2,31L))::validate).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(evidenceWithNormalSentinels(Map.of(0,11L,1,21L))::validate).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(evidenceWithNormalSentinels(Map.of(0,11L,1,21L,3,31L))::validate).isInstanceOf(IllegalArgumentException.class);
    }

    private static CanalRecoveryEvidence valid() {
        UUID anchor = UUID.randomUUID(), normal = UUID.randomUUID();
        Map<Integer,Long> vector = Map.of(0,10L,1,20L,2,30L);
        return new CanalRecoveryEvidence(UUID.randomUUID(), "/cursor/meta.dat", "/evidence/meta.dat",
                "a".repeat(64), "mysql-bin.000001", 500,
                List.of(new CanalRecoveryEvidence.ManifestEntry(2,"mysql-bin.000002"),
                        new CanalRecoveryEvidence.ManifestEntry(3,"mysql-bin.000003")),
                "mysql-bin.000002",2,700,"b".repeat(64),"mysql-bin.000002",2,800,
                anchor,vector,sentinels(anchor,vector),vector,"b".repeat(64),"mysql-bin.000002",2,800,
                vector,normal,increment(vector),sentinels(normal,increment(vector)));
    }

    private static List<CanalRecoveryEvidence.Sentinel> sentinels(UUID runId,Map<Integer,Long> vector) {
        return List.of(new CanalRecoveryEvidence.Sentinel(UUID.randomUUID(),runId,0,vector.get(0)),
                new CanalRecoveryEvidence.Sentinel(UUID.randomUUID(),runId,1,vector.get(1)),
                new CanalRecoveryEvidence.Sentinel(UUID.randomUUID(),runId,2,vector.get(2)));
    }

    private static CanalRecoveryEvidence copy(CanalRecoveryEvidence e, Map<Integer,Long> after) {
        return new CanalRecoveryEvidence(e.recoveryId(),e.cursorPath(),e.cursorBackupPath(),e.oldCursorSha256(),
                e.oldJournalName(),e.oldPosition(),e.retainedManifest(),e.resetLowerBoundJournal(),
                e.resetLowerBoundFileIndex(),e.resetLowerBoundPosition(),e.resetCursorSha256(),
                e.resetJournalName(),e.resetFileIndex(),e.resetPosition(),e.resetAnchorRunId(),
                e.resetAnchorOffsets(),e.resetAnchorEvents(),e.resetRestartOffsetsBefore(),
                e.normalRestartCursorSha256(),e.normalRestartJournalName(),e.normalRestartFileIndex(),
                e.normalRestartPosition(),after,e.normalSentinelRunId(),e.normalSentinelOffsets(),
                e.normalSentinelEvents());
    }
    private static CanalRecoveryEvidence evidenceWithNormalSentinels(Map<Integer,Long> sentinels) {
        CanalRecoveryEvidence e=valid();
        return new CanalRecoveryEvidence(e.recoveryId(),e.cursorPath(),e.cursorBackupPath(),e.oldCursorSha256(),
                e.oldJournalName(),e.oldPosition(),e.retainedManifest(),e.resetLowerBoundJournal(),
                e.resetLowerBoundFileIndex(),e.resetLowerBoundPosition(),e.resetCursorSha256(),
                e.resetJournalName(),e.resetFileIndex(),e.resetPosition(),e.resetAnchorRunId(),
                e.resetAnchorOffsets(),e.resetAnchorEvents(),e.resetRestartOffsetsBefore(),
                e.normalRestartCursorSha256(),e.normalRestartJournalName(),e.normalRestartFileIndex(),
                e.normalRestartPosition(),e.normalRestartOffsetsAfter(),e.normalSentinelRunId(),sentinels,
                sentinels.keySet().equals(java.util.Set.of(0,1,2))?sentinels(e.normalSentinelRunId(),sentinels):e.normalSentinelEvents());
    }
    private static Map<Integer,Long> increment(Map<Integer,Long> vector){return Map.of(0,vector.get(0)+1,1,vector.get(1)+1,2,vector.get(2)+1);}
}
