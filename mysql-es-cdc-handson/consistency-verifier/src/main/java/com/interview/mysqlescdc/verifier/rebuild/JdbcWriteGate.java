package com.interview.mysqlescdc.verifier.rebuild;

import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

@Component
public final class JdbcWriteGate implements WriteGate {
    private final JdbcClient jdbc;
    private final TransactionTemplate transactions;
    public JdbcWriteGate(JdbcClient jdbc, TransactionTemplate transactions) {
        this.jdbc = jdbc; this.transactions = transactions;
    }
    @Override public WriteGateLease close(UUID runId, String reason) {
        if (runId == null || reason == null || reason.isBlank()) throw new IllegalArgumentException("runId and reason required");
        return transactions.execute(status -> {
            GateRow row = lock();
            if (row.closed() && !runId.toString().equals(row.ownerRunId()))
                throw new IllegalStateException("write gate owned by another run");
            jdbc.sql("UPDATE product_write_gate SET closed=TRUE, owner_run_id=UUID_TO_BIN(:run), reason=:reason WHERE singleton_id=1")
                    .param("run", runId.toString()).param("reason", reason).update();
            return new WriteGateLease(runId, reason);
        });
    }
    @Override public void open(UUID runId) {
        transactions.executeWithoutResult(status -> {
            GateRow row = lock();
            if (!row.closed() && row.ownerRunId() == null) return;
            if (!runId.toString().equals(row.ownerRunId())) throw new IllegalStateException("write gate owned by another run");
            jdbc.sql("UPDATE product_write_gate SET closed=FALSE, owner_run_id=NULL, reason=NULL WHERE singleton_id=1").update();
        });
    }
    private GateRow lock() {
        return jdbc.sql("SELECT closed, BIN_TO_UUID(owner_run_id) owner_run_id FROM product_write_gate WHERE singleton_id=1 FOR UPDATE")
                .query(GateRow.class).single();
    }
    record GateRow(boolean closed, String ownerRunId) {}
}
