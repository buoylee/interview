package com.interview.mysqlescdc.verifier.status;

import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;

@Component
public final class RefuseUnprovenRebuildEvidence implements SuccessfulRebuildEvidence {
    private final JdbcClient jdbc;

    public RefuseUnprovenRebuildEvidence(JdbcClient jdbc) { this.jdbc = jdbc; }

    @Override
    public boolean isSuccessfulRebuild(UUID rebuildRunId) {
        if (rebuildRunId == null) return false;
        return jdbc.sql("""
                SELECT COUNT(*) FROM rebuild_run r
                JOIN verification_run v ON v.run_id=r.verification_run_id
                WHERE r.run_id=UUID_TO_BIN(:run)
                  AND r.status IN ('CUTOVER_COMMITTED','COMPLETED')
                  AND r.alias_swapped=TRUE
                  AND v.status='PASS' AND v.difference_count=0
                  AND v.source_watermark_start=v.source_watermark_end
                """).param("run", rebuildRunId.toString()).query(Long.class).single() == 1L;
    }
}
