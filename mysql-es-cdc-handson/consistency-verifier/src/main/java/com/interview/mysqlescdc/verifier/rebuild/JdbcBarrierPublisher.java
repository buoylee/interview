package com.interview.mysqlescdc.verifier.rebuild;

import java.util.LinkedHashSet;
import java.util.Set;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class JdbcBarrierPublisher implements BarrierPublisher {
    private final JdbcClient jdbc;
    public JdbcBarrierPublisher(JdbcClient jdbc) { this.jdbc = jdbc; }
    @Override @Transactional
    public Barrier publish(UUID runId, int partitions) {
        if (partitions != 3) throw new IllegalArgumentException("v1 barrier contract requires exactly 3 partitions");
        Set<String> tokens = new LinkedHashSet<>();
        for (int partition=0; partition<partitions; partition++) {
            String token = Integer.toString(partition);
            if (Math.floorMod(token.hashCode(), partitions) != partition) throw new IllegalStateException("barrier token routing mismatch");
            jdbc.sql("INSERT INTO cdc_barrier(run_id, partition_token) VALUES(UUID_TO_BIN(:run), :token)")
                    .param("run", runId.toString()).param("token", token).update();
            tokens.add(token);
        }
        return new Barrier(runId, tokens);
    }
}
