package com.interview.mysqlescdc.verifier.rebuild;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

public record CanalRecoveryEvidence(
        UUID recoveryId,
        String cursorPath,
        String cursorBackupPath,
        String oldCursorSha256,
        String oldJournalName,
        long oldPosition,
        List<ManifestEntry> retainedManifest,
        String resetLowerBoundJournal,
        int resetLowerBoundFileIndex,
        long resetLowerBoundPosition,
        String resetCursorSha256,
        String resetJournalName,
        int resetFileIndex,
        long resetPosition,
        UUID resetAnchorRunId,
        Map<Integer, Long> resetAnchorOffsets,
        List<Sentinel> resetAnchorEvents,
        Map<Integer, Long> resetRestartOffsetsBefore,
        String normalRestartCursorSha256,
        String normalRestartJournalName,
        int normalRestartFileIndex,
        long normalRestartPosition,
        Map<Integer, Long> normalRestartOffsetsAfter,
        UUID normalSentinelRunId,
        Map<Integer, Long> normalSentinelOffsets,
        List<Sentinel> normalSentinelEvents) {

    public record ManifestEntry(int fileIndex, String journal) {}
    public record Sentinel(UUID eventId, UUID runId, int partition, long nextOffset) {}

    public void validate() {
        required(recoveryId, cursorPath, cursorBackupPath, oldCursorSha256, oldJournalName,
                retainedManifest, resetLowerBoundJournal, resetCursorSha256, resetJournalName,
                resetAnchorRunId, normalRestartCursorSha256, normalRestartJournalName,
                normalSentinelRunId);
        hash(oldCursorSha256); hash(resetCursorSha256); hash(normalRestartCursorSha256);
        if (oldPosition < 0 || resetLowerBoundPosition < 0 || resetPosition < 0) invalid();
        manifestAt(resetLowerBoundFileIndex, resetLowerBoundJournal);
        manifestAt(resetFileIndex, resetJournalName);
        manifestAt(normalRestartFileIndex, normalRestartJournalName);
        if (retainedManifest.stream().anyMatch(entry -> oldJournalName.equals(entry.journal()))) invalid();
        if (resetCursorSha256.equals(oldCursorSha256)) invalid();
        if (compare(resetFileIndex, resetPosition, resetLowerBoundFileIndex, resetLowerBoundPosition) < 0) invalid();
        if (!resetCursorSha256.equals(normalRestartCursorSha256)
                || resetFileIndex != normalRestartFileIndex || resetPosition != normalRestartPosition
                || !resetJournalName.equals(normalRestartJournalName)) invalid();
        vector(resetAnchorOffsets); vector(resetRestartOffsetsBefore);
        vector(normalRestartOffsetsAfter); vector(normalSentinelOffsets);
        if (!resetAnchorOffsets.equals(resetRestartOffsetsBefore)
                || !resetAnchorOffsets.equals(normalRestartOffsetsAfter)) invalid();
        if (resetAnchorRunId.equals(normalSentinelRunId)) invalid();
        for (int partition : Set.of(0, 1, 2)) {
            if (normalSentinelOffsets.get(partition) <= normalRestartOffsetsAfter.get(partition)) invalid();
        }
        sentinels(resetAnchorEvents, resetAnchorRunId, resetAnchorOffsets);
        sentinels(normalSentinelEvents, normalSentinelRunId, normalSentinelOffsets);
    }

    private void manifestAt(int index, String journal) {
        long matches = retainedManifest.stream()
                .filter(entry -> entry.fileIndex() == index && journal.equals(entry.journal())).count();
        if (matches != 1) invalid();
        for (int i = 1; i < retainedManifest.size(); i++) {
            if (retainedManifest.get(i - 1).fileIndex() >= retainedManifest.get(i).fileIndex()) invalid();
        }
    }

    private static void sentinels(List<Sentinel> events, UUID runId, Map<Integer, Long> vector) {
        if (events == null || events.size() != 3
                || events.stream().map(Sentinel::eventId).distinct().count() != 3
                || !events.stream().map(Sentinel::partition).collect(java.util.stream.Collectors.toSet()).equals(Set.of(0, 1, 2))) invalid();
        for (Sentinel event : events) {
            if (event.eventId() == null || !runId.equals(event.runId())
                    || event.nextOffset() != vector.get(event.partition())) invalid();
        }
        if (runId == null) invalid();
    }

    private static void vector(Map<Integer, Long> vector) {
        if (vector == null || !vector.keySet().equals(Set.of(0, 1, 2))
                || vector.values().stream().anyMatch(value -> value == null || value < 0)) invalid();
    }

    private static int compare(int leftIndex, long leftPosition, int rightIndex, long rightPosition) {
        int files = Integer.compare(leftIndex, rightIndex);
        return files == 0 ? Long.compare(leftPosition, rightPosition) : files;
    }

    private static void hash(String value) { if (value == null || !value.matches("[0-9a-f]{64}")) invalid(); }
    private static void required(Object... values) { for (Object value : values) if (value == null) invalid(); }
    private static void invalid() { throw new IllegalArgumentException("incomplete or contradictory Canal recovery evidence"); }
}
