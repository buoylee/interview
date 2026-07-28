package com.interview.mysqlescdc.verifier.repair;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.interview.mysqlescdc.verifier.diff.DifferenceType;
import com.interview.mysqlescdc.verifier.diff.DocumentDifference;
import com.interview.mysqlescdc.verifier.run.StoredVerificationRun;
import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;
import com.interview.mysqlescdc.verifier.run.VerificationRunStore;
import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.source.ExpectedDocumentReader;
import com.interview.mysqlescdc.verifier.source.SourceWatermarkReader;

@Service
public final class RepairService {
    private static final String LOG_GAP = "LOG_GAP";
    private static final String REBUILD_REQUIRED = "REBUILD_REQUIRED";

    private final VerificationRunStore store;
    private final SourceWatermarkReader watermark;
    private final ExpectedDocumentReader source;
    private final RepairGateway gateway;
    private final int repairLimit;

    public RepairService(
            VerificationRunStore store,
            SourceWatermarkReader watermark,
            ExpectedDocumentReader source,
            RepairGateway gateway,
            @Value("${verification.repair-limit:100}") int repairLimit) {
        this.store = store;
        this.watermark = watermark;
        this.source = source;
        this.gateway = gateway;
        if (repairLimit < 1 || repairLimit > 100) {
            throw new IllegalArgumentException("repair limit must be between 1 and 100");
        }
        this.repairLimit = repairLimit;
    }

    public RepairReport repair(UUID runId) {
        StoredVerificationRun run = store.findRun(runId)
                .orElseThrow(() -> new IllegalArgumentException("verification run not found"));
        if (run.status() != VerificationRunStatus.DIFF) {
            throw new IllegalStateException("only a conclusive DIFF run can be repaired");
        }
        if (run.sourceWatermarkEnd() == null
                || run.sourceWatermarkEnd() != run.sourceWatermarkStart()) {
            throw new IllegalStateException("repair requires an unchanged verification watermark");
        }
        if (run.differenceCount() > repairLimit) {
            throw new IllegalStateException("difference count exceeds bounded repair limit");
        }
        if (store.conditionActive(LOG_GAP)) {
            throw new IllegalStateException("active LOG_GAP blocks repair");
        }
        List<DocumentDifference> differences = store.loadDifferences(runId, repairLimit + 1);
        if (differences.size() > repairLimit || differences.size() != run.differenceCount()) {
            throw new IllegalStateException("persisted difference set is incomplete or over limit");
        }
        if (differences.stream().anyMatch(this::requiresRebuild)) {
            store.activateCondition(REBUILD_REQUIRED,
                    "{\"reason\":\"unsafe_reconciliation_difference\"}");
            throw new IllegalStateException("difference requires rebuild, not in-place repair");
        }

        long start = watermark.current();
        int applied = 0;
        int stale = 0;
        int skipped = 0;
        int failed = 0;
        for (DocumentDifference difference : differences) {
            if (watermark.current() != start) break;
            Optional<RepairActionRecord> existing =
                    store.findRepairAction(runId, difference.productId());
            if (existing.isPresent()
                    && (existing.get().outcome() == RepairOutcome.APPLIED
                    || existing.get().outcome() == RepairOutcome.STALE)) {
                skipped++;
                continue;
            }

            RepairActionType type = actionType(difference.type());
            ExpectedDocument current = null;
            Long sourceRevision = null;
            if (type != RepairActionType.DELETE_EXTRA) {
                current = source.load(difference.productId()).orElseThrow(() ->
                        new IllegalStateException("current source row missing during repair"));
                sourceRevision = current.sourceRevision();
                if (watermark.current() != start) break;
            }
            UUID actionId = existing.map(RepairActionRecord::actionId).orElseGet(UUID::randomUUID);
            store.markActionStarted(
                    actionId, runId, difference.productId(), type, start, sourceRevision);
            try {
                RepairOutcome outcome = type == RepairActionType.DELETE_EXTRA
                        ? gateway.deleteExtra(run.target(), difference.actual())
                        : gateway.write(run.target(), type, current);
                if (outcome != RepairOutcome.APPLIED && outcome != RepairOutcome.STALE) {
                    throw new IllegalStateException("repair gateway returned non-terminal outcome");
                }
                store.finishAction(actionId, outcome, null);
                store.markDifferenceRepaired(runId, difference.productId(), outcome.name());
                if (outcome == RepairOutcome.APPLIED) applied++; else stale++;
            } catch (RuntimeException exception) {
                failed++;
                store.finishAction(actionId, RepairOutcome.FAILED, bounded(exception.getMessage()));
                break;
            }
        }
        long end = watermark.current();
        boolean stable = end == start;
        boolean repaired = stable && failed == 0 && applied + stale + skipped == differences.size();
        if (repaired) store.markRunRepaired(runId);
        return new RepairReport(
                runId, start, end, applied, stale, skipped, failed, stable, repaired);
    }

    private boolean requiresRebuild(DocumentDifference difference) {
        return difference.type() == DifferenceType.FUTURE_REVISION
                || difference.type() == DifferenceType.VERSION_METADATA_MISMATCH;
    }

    private RepairActionType actionType(DifferenceType type) {
        return switch (type) {
            case STALE -> RepairActionType.WRITE_EXTERNAL;
            case MISSING, MODIFIED, TOMBSTONE_MISMATCH -> RepairActionType.WRITE_EXTERNAL_GTE;
            case EXTRA -> RepairActionType.DELETE_EXTRA;
            case FUTURE_REVISION, VERSION_METADATA_MISMATCH ->
                    throw new IllegalStateException("unsafe difference requires rebuild");
        };
    }

    private String bounded(String value) {
        String safe = value == null || value.isBlank() ? "repair failed" : value;
        return safe.length() <= 512 ? safe : safe.substring(0, 512);
    }
}
