package com.interview.mysqlescdc.verifier.rebuild;

import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public final class CanalRecoveryBarrierService {
    private final JdbcClient jdbc;
    private final BarrierPublisher publisher;
    private final TransactionTemplate transactions;

    public CanalRecoveryBarrierService(JdbcClient jdbc, BarrierPublisher publisher,
            TransactionTemplate transactions) {
        this.jdbc=jdbc;this.publisher=publisher;this.transactions=transactions;
    }

    public Barrier publish(UUID rebuildRunId, UUID markerRunId) {
        if (rebuildRunId==null || markerRunId==null || rebuildRunId.equals(markerRunId)) {
            throw new IllegalArgumentException("distinct rebuild and marker run IDs required");
        }
        return transactions.execute(status -> {
            Ownership evidence=jdbc.sql("""
                    SELECT r.status,g.closed,BIN_TO_UUID(g.owner_run_id) owner
                    FROM rebuild_run r JOIN product_write_gate g ON g.singleton_id=1
                    WHERE r.run_id=UUID_TO_BIN(:run) FOR UPDATE
                    """).param("run",rebuildRunId.toString()).query(Ownership.class).single();
            if (!"CANAL_RECOVERING".equals(evidence.status()) || !evidence.closed()
                    || !rebuildRunId.toString().equals(evidence.owner())) {
                throw new IllegalStateException("gate-owned CANAL_RECOVERING run required");
            }
            return publisher.publish(markerRunId,3);
        });
    }

    private record Ownership(String status, boolean closed, String owner) {}
}
