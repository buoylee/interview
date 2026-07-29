package com.interview.mysqlescdc.verifier.rebuild;

import java.util.UUID;
import java.util.Map;
import java.time.Duration;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public final class CanalRecoveryBarrierService {
    private final JdbcClient jdbc;
    private final BarrierPublisher publisher;
    private final TransactionTemplate transactions;
    private final RecoveryBarrierObserver observer;
    private final tools.jackson.databind.json.JsonMapper json = tools.jackson.databind.json.JsonMapper.builder().build();

    public CanalRecoveryBarrierService(JdbcClient jdbc, BarrierPublisher publisher,
            TransactionTemplate transactions, RecoveryBarrierObserver observer) {
        this.jdbc=jdbc;this.publisher=publisher;this.transactions=transactions;this.observer=observer;
    }

    public RecoveryBarrierObservation publishAndObserve(UUID rebuildRunId, UUID markerRunId,
            String kind, Map<Integer,Long> preOffsets) {
        if (rebuildRunId==null || markerRunId==null || rebuildRunId.equals(markerRunId)) {
            throw new IllegalArgumentException("distinct rebuild and marker run IDs required");
        }
        Barrier barrier = transactions.execute(status -> {
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
        RecoveryBarrierObservation observation=observer.observe("product-search-revisions",kind,
                barrier,preOffsets,Duration.ofSeconds(60));
        try {
            int inserted=jdbc.sql("""
                    INSERT INTO canal_recovery_observation(rebuild_run_id,kind,marker_run_id,
                      pre_offsets_json,observed_offsets_json,events_json)
                    VALUES(UUID_TO_BIN(:run),:kind,UUID_TO_BIN(:marker),CAST(:pre AS JSON),
                      CAST(:offsets AS JSON),CAST(:events AS JSON))
                    """).param("run",rebuildRunId.toString()).param("kind",kind)
                    .param("marker",markerRunId.toString())
                    .param("pre",json.writeValueAsString(preOffsets))
                    .param("offsets",json.writeValueAsString(observation.offsets()))
                    .param("events",json.writeValueAsString(observation.events())).update();
            if(inserted!=1)throw new IllegalStateException("recovery observation persistence lost");
        } catch(RuntimeException failure){throw failure;}
        catch(Exception failure){throw new IllegalStateException("recovery observation serialization failed",failure);}
        return observation;
    }

    private record Ownership(String status, boolean closed, String owner) {}
}
