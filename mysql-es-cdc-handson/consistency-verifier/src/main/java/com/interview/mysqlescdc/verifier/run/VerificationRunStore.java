package com.interview.mysqlescdc.verifier.run;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import com.interview.mysqlescdc.verifier.diff.ConsistencyReport;
import com.interview.mysqlescdc.verifier.diff.DocumentDifference;
import com.interview.mysqlescdc.verifier.repair.RepairActionRecord;
import com.interview.mysqlescdc.verifier.repair.RepairActionType;
import com.interview.mysqlescdc.verifier.repair.RepairOutcome;

public interface VerificationRunStore {
    void createRunning(UUID runId, String target, long sourceWatermarkStart);

    void appendDifference(UUID runId, DocumentDifference difference);

    void complete(UUID runId, VerificationRunStatus status, long sourceWatermarkEnd,
            ConsistencyReport report);

    void fail(UUID runId, String failureClass, String boundedMessage);

    Optional<StoredVerificationRun> findRun(UUID runId);

    Optional<VerificationRunReport> findReport(UUID runId);

    List<DocumentDifference> loadDifferences(UUID runId, int limitPlusOne);

    boolean hasUnsafeDifferences(UUID runId);

    boolean conditionActive(String conditionKey);

    void activateCondition(String conditionKey, String detailsJson);

    Optional<RepairActionRecord> findRepairAction(UUID runId, long productId);

    void markActionStarted(UUID actionId, UUID runId, long productId,
            RepairActionType type, long sourceWatermark, Long sourceRevision);

    void finishAction(UUID actionId, RepairOutcome outcome, String errorMessage);

    boolean markDifferenceRepaired(UUID runId, long productId, String outcome);

    void markRunRepaired(UUID runId);
}
