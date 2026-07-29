package com.interview.mysqlescdc.verifier.rebuild;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class JdbcRebuildRunStore implements RebuildRunStore {
    private static final DateTimeFormatter STAMP = DateTimeFormatter
            .ofPattern("yyyyMMddHHmmss").withZone(ZoneOffset.UTC);
    private final JdbcClient jdbc;

    public JdbcRebuildRunStore(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional
    public void create(RebuildRequest request) {
        long active = jdbc.sql("""
                SELECT COUNT(*) FROM rebuild_run WHERE status NOT IN ('COMPLETED','FAILED')
                """).query(Long.class).single();
        if (active != 0) throw new IllegalStateException("one nonterminal rebuild allowed");
        String name = "products_v3_" + STAMP.format(Instant.now()) + "_"
                + request.runId().toString().substring(0, 8);
        int inserted = jdbc.sql("""
                INSERT INTO rebuild_run(
                  run_id,generation_name,topic_name,rebuild_reason,page_size,status)
                VALUES(UUID_TO_BIN(:run),:name,:topic,:reason,:page,'CREATED')
                """)
                .param("run", request.runId().toString()).param("name", name)
                .param("topic", request.topic()).param("reason", request.reason())
                .param("page", request.pageSize()).update();
        if (inserted != 1) throw new IllegalStateException("rebuild create lost");

        jdbc.sql("""
                UPDATE pipeline_condition
                SET owner_rebuild_run_id = UUID_TO_BIN(:run)
                WHERE active = TRUE AND owner_rebuild_run_id IS NULL
                  AND (condition_key = 'REBUILD_REQUIRED'
                    OR (:claimLogGap = TRUE AND condition_key = 'LOG_GAP'))
                """).param("run", request.runId().toString())
                .param("claimLogGap", !"NORMAL".equals(request.reason())).update();
        jdbc.sql("""
                INSERT INTO pipeline_condition(
                  condition_key,active,details_json,observed_at,cleared_at,owner_rebuild_run_id)
                VALUES('REBUILD_IN_PROGRESS',TRUE,JSON_OBJECT('rebuildRunId',:run),
                       CURRENT_TIMESTAMP(6),NULL,UUID_TO_BIN(:run))
                ON DUPLICATE KEY UPDATE active=TRUE,details_json=VALUES(details_json),
                  observed_at=VALUES(observed_at),cleared_at=NULL,
                  owner_rebuild_run_id=VALUES(owner_rebuild_run_id)
                """).param("run", request.runId().toString()).update();
    }

    @Transactional
    public void transition(UUID run, String expected, String next) {
        int updated = jdbc.sql("""
                UPDATE rebuild_run
                SET status=:next,
                    alias_swapped=IF(:next='CUTOVER_COMMITTED',TRUE,alias_swapped),
                    finished_at=IF(:next='COMPLETED',CURRENT_TIMESTAMP(6),finished_at)
                WHERE run_id=UUID_TO_BIN(:run) AND status=:expected
                """).param("next", next).param("run", run.toString())
                .param("expected", expected).update();
        if (updated != 1) throw new IllegalStateException(
                "rebuild transition lost " + expected + " -> " + next);
        if ("COMPLETED".equals(next)) clearInProgress(run);
    }

    @Transactional
    public void fail(UUID run, Throwable failure) {
        String message = failure.getMessage() == null
                ? failure.getClass().getSimpleName() : failure.getMessage();
        if (message.length() > 512) message = message.substring(0, 512);
        int updated = jdbc.sql("""
                UPDATE rebuild_run
                SET status='FAILED',failure_phase=status,failure_message=:message,
                    finished_at=CURRENT_TIMESTAMP(6)
                WHERE run_id=UUID_TO_BIN(:run)
                  AND status NOT IN ('COMPLETED','FAILED','CUTOVER_COMMITTED')
                """).param("message", message).param("run", run.toString()).update();
        if (updated != 1) failure.addSuppressed(
                new IllegalStateException("failed to persist rebuild failure"));
        else clearInProgress(run);
    }

    public RebuildStatus get(UUID run) {
        RunRow row = jdbc.sql("""
                SELECT BIN_TO_UUID(run_id) runId,status,generation_name generation,
                       failure_message failureMessage,alias_swapped aliasSwapped,
                       BIN_TO_UUID(verification_run_id) verificationRunId
                FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)
                """).param("run", run.toString()).query(RunRow.class).single();
        String owner = jdbc.sql("""
                SELECT BIN_TO_UUID(owner_run_id) FROM product_write_gate WHERE singleton_id=1
                """).query(String.class).optional().orElse(null);
        return new RebuildStatus(row.runId(), row.status(), row.generation(),
                row.failureMessage(), row.aliasSwapped(), phase(run, "START"),
                phase(run, "SHADOW"), phase(run, "BARRIER"), row.verificationRunId(),
                owner, row.aliasSwapped() ? "NEW" : "OLD");
    }

    private Map<Integer, Long> phase(UUID run, String phase) {
        Map<Integer, Long> values = new LinkedHashMap<>();
        jdbc.sql("""
                SELECT partition_id,next_offset FROM rebuild_partition_offset
                WHERE run_id=UUID_TO_BIN(:run) AND phase=:phase ORDER BY partition_id
                """).param("run", run.toString()).param("phase", phase)
                .query((rs, row) -> Map.entry(rs.getInt(1), rs.getLong(2))).list()
                .forEach(entry -> values.put(entry.getKey(), entry.getValue()));
        return Map.copyOf(values);
    }

    private void clearInProgress(UUID run) {
        jdbc.sql("""
                UPDATE pipeline_condition SET active=FALSE,cleared_at=CURRENT_TIMESTAMP(6)
                WHERE condition_key='REBUILD_IN_PROGRESS' AND active=TRUE
                  AND owner_rebuild_run_id=UUID_TO_BIN(:run)
                """).param("run", run.toString()).update();
    }

    public List<UUID> nonterminal() {
        return jdbc.sql("""
                SELECT BIN_TO_UUID(run_id) FROM rebuild_run
                WHERE status NOT IN ('COMPLETED','FAILED') ORDER BY started_at
                """).query(String.class).list().stream().map(UUID::fromString).toList();
    }

    private record RunRow(UUID runId, String status, String generation,
            String failureMessage, boolean aliasSwapped, UUID verificationRunId) {}
}
