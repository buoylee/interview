package com.interview.mysqlescdc.verifier.run;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.Map;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import com.interview.mysqlescdc.verifier.diff.ConsistencyReport;
import com.interview.mysqlescdc.verifier.diff.DifferenceType;
import com.interview.mysqlescdc.verifier.diff.DocumentDifference;
import com.interview.mysqlescdc.verifier.diff.FieldDifference;
import com.interview.mysqlescdc.verifier.repair.RepairActionRecord;
import com.interview.mysqlescdc.verifier.repair.RepairActionType;
import com.interview.mysqlescdc.verifier.repair.RepairOutcome;
import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.target.IndexedDocument;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

@Repository
public class JdbcVerificationRunStore implements VerificationRunStore {
    private final JdbcClient jdbc;
    private final JsonMapper json = JsonMapper.builder().findAndAddModules().build();

    public JdbcVerificationRunStore(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public void createRunning(UUID runId, String target, long sourceWatermarkStart) {
        jdbc.sql("""
                INSERT INTO verification_run(
                  run_id, target_name, status, source_watermark_start)
                VALUES (UUID_TO_BIN(:runId), :target, 'RUNNING', :watermark)
                """).param("runId", runId.toString()).param("target", target)
                .param("watermark", sourceWatermarkStart).update();
    }

    @Override
    public void appendDifference(UUID runId, DocumentDifference difference) {
        jdbc.sql("""
                INSERT INTO verification_difference(
                  run_id, product_id, difference_type, expected_revision, actual_revision,
                  expected_json, actual_json, fields_json)
                VALUES (
                  UUID_TO_BIN(:runId), :productId, :type, :expectedRevision, :actualRevision,
                  CAST(:expectedJson AS JSON), CAST(:actualJson AS JSON), CAST(:fieldsJson AS JSON))
                """)
                .param("runId", runId.toString())
                .param("productId", difference.productId())
                .param("type", difference.type().name())
                .param("expectedRevision", difference.expected() == null
                        ? null : difference.expected().sourceRevision())
                .param("actualRevision", difference.actual() == null
                        ? null : difference.actual().sourceRevision())
                .param("expectedJson", serializeNullable(difference.expected()))
                .param("actualJson", serializeNullable(difference.actual()))
                .param("fieldsJson", serialize(difference.fields()))
                .update();
    }

    @Override
    public void complete(
            UUID runId, VerificationRunStatus status, long sourceWatermarkEnd,
            ConsistencyReport report) {
        int changed = jdbc.sql("""
                UPDATE verification_run
                SET status = :status,
                    source_watermark_end = :watermarkEnd,
                    expected_count = :expectedCount,
                    actual_count = :actualCount,
                    difference_count = :differenceCount,
                    finished_at = CURRENT_TIMESTAMP(6),
                    failure_class = NULL,
                    failure_message = NULL
                WHERE run_id = UUID_TO_BIN(:runId) AND status = 'RUNNING'
                """).param("status", status.name())
                .param("watermarkEnd", sourceWatermarkEnd)
                .param("expectedCount", report.expectedCount())
                .param("actualCount", report.actualCount())
                .param("differenceCount", report.differenceCount())
                .param("runId", runId.toString()).update();
        requireOne(changed, "complete verification run");
    }

    @Override
    public void fail(UUID runId, String failureClass, String boundedMessage) {
        int changed = jdbc.sql("""
                UPDATE verification_run
                SET status = 'FAILED', finished_at = CURRENT_TIMESTAMP(6),
                    failure_class = :failureClass, failure_message = :failureMessage
                WHERE run_id = UUID_TO_BIN(:runId) AND status = 'RUNNING'
                """).param("failureClass", failureClass).param("failureMessage", boundedMessage)
                .param("runId", runId.toString()).update();
        requireOne(changed, "fail verification run");
    }

    @Override
    public Optional<StoredVerificationRun> findRun(UUID runId) {
        return jdbc.sql("""
                SELECT BIN_TO_UUID(run_id) AS run_id, target_name, status,
                       source_watermark_start, source_watermark_end, difference_count
                FROM verification_run WHERE run_id = UUID_TO_BIN(:runId)
                """).param("runId", runId.toString()).query((rs, row) -> new StoredVerificationRun(
                        UUID.fromString(rs.getString("run_id")), rs.getString("target_name"),
                        VerificationRunStatus.valueOf(rs.getString("status")),
                        rs.getLong("source_watermark_start"), nullableLong(rs, "source_watermark_end"),
                        rs.getLong("difference_count"))).optional();
    }

    @Override
    public Optional<VerificationRunReport> findReport(UUID runId) {
        Optional<VerificationRunReport> report = jdbc.sql("""
                SELECT BIN_TO_UUID(run_id) AS run_id, target_name, status,
                       source_watermark_start, source_watermark_end,
                       expected_count, actual_count, difference_count,
                       failure_class, failure_message
                FROM verification_run WHERE run_id = UUID_TO_BIN(:runId)
                """).param("runId", runId.toString()).query((rs, row) ->
                        new VerificationRunReport(
                                UUID.fromString(rs.getString("run_id")),
                                rs.getString("target_name"),
                                VerificationRunStatus.valueOf(rs.getString("status")),
                                rs.getLong("source_watermark_start"),
                                nullableLong(rs, "source_watermark_end"),
                                rs.getLong("expected_count"), rs.getLong("actual_count"),
                                rs.getLong("difference_count"), Map.of(),
                                rs.getString("failure_class"), rs.getString("failure_message")))
                .optional();
        if (report.isEmpty()) return report;
        Map<DifferenceType, Long> counts = new EnumMap<>(DifferenceType.class);
        jdbc.sql("""
                SELECT difference_type, COUNT(*) AS count
                FROM verification_difference
                WHERE run_id = UUID_TO_BIN(:runId) GROUP BY difference_type
                """).param("runId", runId.toString()).query((rs, row) -> {
                    counts.put(DifferenceType.valueOf(rs.getString("difference_type")),
                            rs.getLong("count"));
                    return 0;
                }).list();
        VerificationRunReport value = report.get();
        return Optional.of(new VerificationRunReport(
                value.runId(), value.target(), value.status(), value.sourceWatermarkStart(),
                value.sourceWatermarkEnd(), value.expectedCount(), value.actualCount(),
                value.differenceCount(), counts, value.failureClass(), value.failureMessage()));
    }

    @Override
    public List<DocumentDifference> loadDifferences(UUID runId, int limitPlusOne) {
        return jdbc.sql("""
                SELECT product_id, difference_type, expected_json, actual_json, fields_json
                FROM verification_difference
                WHERE run_id = UUID_TO_BIN(:runId)
                ORDER BY product_id, difference_type
                LIMIT :limit
                """).param("runId", runId.toString()).param("limit", limitPlusOne)
                .query(this::mapDifference).list();
    }

    @Override
    public boolean hasUnsafeDifferences(UUID runId) {
        return jdbc.sql("""
                SELECT EXISTS(
                  SELECT 1 FROM verification_difference
                  WHERE run_id = UUID_TO_BIN(:runId)
                    AND difference_type IN ('FUTURE_REVISION', 'VERSION_METADATA_MISMATCH'))
                """).param("runId", runId.toString()).query(Boolean.class).single();
    }

    @Override
    public boolean conditionActive(String conditionKey) {
        return jdbc.sql("SELECT active FROM pipeline_condition WHERE condition_key = :key")
                .param("key", conditionKey).query(Boolean.class).optional().orElse(false);
    }

    @Override
    public void activateCondition(String conditionKey, String detailsJson) {
        jdbc.sql("""
                INSERT INTO pipeline_condition(condition_key, active, details_json, observed_at, cleared_at, owner_rebuild_run_id)
                VALUES (:key, TRUE, CAST(:details AS JSON), CURRENT_TIMESTAMP(6), NULL, NULL)
                ON DUPLICATE KEY UPDATE active = TRUE, details_json = VALUES(details_json),
                  observed_at = VALUES(observed_at), cleared_at = NULL, owner_rebuild_run_id = NULL
                """).param("key", conditionKey).param("details", detailsJson).update();
    }

    @Override
    public Optional<RepairActionRecord> findRepairAction(UUID runId, long productId) {
        return jdbc.sql("""
                SELECT BIN_TO_UUID(action_id) AS action_id, product_id, action_type, outcome
                FROM repair_action
                WHERE run_id = UUID_TO_BIN(:runId) AND product_id = :productId
                """).param("runId", runId.toString()).param("productId", productId)
                .query((rs, row) -> new RepairActionRecord(
                        UUID.fromString(rs.getString("action_id")), rs.getLong("product_id"),
                        RepairActionType.valueOf(rs.getString("action_type")),
                        RepairOutcome.valueOf(rs.getString("outcome")))).optional();
    }

    @Override
    public void markActionStarted(
            UUID actionId, UUID runId, long productId, RepairActionType type,
            long sourceWatermark, Long sourceRevision) {
        jdbc.sql("""
                INSERT INTO repair_action(
                  action_id, run_id, product_id, action_type, source_watermark,
                  source_revision, outcome)
                VALUES (UUID_TO_BIN(:actionId), UUID_TO_BIN(:runId), :productId, :type,
                        :watermark, :revision, 'STARTED')
                ON DUPLICATE KEY UPDATE action_type = VALUES(action_type),
                  source_watermark = VALUES(source_watermark),
                  source_revision = VALUES(source_revision), outcome = 'STARTED',
                  started_at = CURRENT_TIMESTAMP(6), finished_at = NULL, error_message = NULL
                """).param("actionId", actionId.toString()).param("runId", runId.toString())
                .param("productId", productId).param("type", type.name())
                .param("watermark", sourceWatermark).param("revision", sourceRevision).update();
    }

    @Override
    public void finishAction(UUID actionId, RepairOutcome outcome, String errorMessage) {
        int changed = jdbc.sql("""
                UPDATE repair_action
                SET outcome = :outcome, finished_at = CURRENT_TIMESTAMP(6), error_message = :error
                WHERE action_id = UUID_TO_BIN(:actionId) AND outcome = 'STARTED'
                """).param("outcome", outcome.name()).param("error", bounded(errorMessage, 512))
                .param("actionId", actionId.toString()).update();
        requireOne(changed, "finish repair action");
    }

    @Override
    public boolean markDifferenceRepaired(UUID runId, long productId, String outcome) {
        jdbc.sql("""
                UPDATE verification_difference
                SET repaired_at = CURRENT_TIMESTAMP(6), repair_outcome = :outcome
                WHERE run_id = UUID_TO_BIN(:runId) AND product_id = :productId
                  AND repaired_at IS NULL
                """).param("outcome", outcome).param("runId", runId.toString())
                .param("productId", productId).update();
        return jdbc.sql("""
                SELECT EXISTS(
                  SELECT 1 FROM verification_difference
                  WHERE run_id = UUID_TO_BIN(:runId) AND product_id = :productId
                    AND repaired_at IS NOT NULL AND repair_outcome = :outcome)
                """).param("outcome", outcome).param("runId", runId.toString())
                .param("productId", productId).query(Boolean.class).single();
    }

    @Override
    public void markRunRepaired(UUID runId) {
        int changed = jdbc.sql("""
                UPDATE verification_run SET status = 'REPAIRED', finished_at = CURRENT_TIMESTAMP(6)
                WHERE run_id = UUID_TO_BIN(:runId) AND status = 'DIFF'
                """).param("runId", runId.toString()).update();
        requireOne(changed, "mark run repaired");
    }

    private DocumentDifference mapDifference(ResultSet rs, int row) throws SQLException {
        return new DocumentDifference(
                rs.getLong("product_id"), DifferenceType.valueOf(rs.getString("difference_type")),
                parseExpected(rs.getString("expected_json")),
                parseActual(rs.getString("actual_json")),
                parseFields(rs.getString("fields_json")));
    }

    private ExpectedDocument parseExpected(String payload) {
        if (payload == null) return null;
        JsonNode node = parse(payload);
        return new ExpectedDocument(
                node.path("productId").longValue(), text(node, "sku"), text(node, "name"),
                text(node, "description"), boxedLong(node, "categoryId"), text(node, "categoryName"),
                boxedLong(node, "priceCents"), boxedInt(node, "availableQuantity"),
                node.path("searchable").booleanValue(), node.path("sourceRevision").longValue(),
                Instant.parse(node.path("sourceUpdatedAt").textValue()));
    }

    private IndexedDocument parseActual(String payload) {
        if (payload == null) return null;
        JsonNode node = parse(payload);
        return new IndexedDocument(
                node.path("productId").longValue(), text(node, "sku"), text(node, "name"),
                text(node, "description"), boxedLong(node, "categoryId"), text(node, "categoryName"),
                boxedLong(node, "priceCents"), boxedInt(node, "availableQuantity"),
                node.path("searchable").booleanValue(), node.path("sourceRevision").longValue(),
                instant(node, "sourceUpdatedAt"), node.path("elasticsearchVersion").longValue(),
                node.path("sequenceNumber").longValue(), node.path("primaryTerm").longValue());
    }

    private List<FieldDifference> parseFields(String payload) {
        List<FieldDifference> fields = new ArrayList<>();
        for (JsonNode node : parse(payload)) {
            fields.add(new FieldDifference(node.path("field").textValue(),
                    node.path("expectedValue").deepCopy(), node.path("actualValue").deepCopy()));
        }
        return fields;
    }

    private JsonNode parse(String payload) {
        try {
            return json.readTree(payload);
        } catch (JacksonException exception) {
            throw new IllegalStateException("invalid persisted verification JSON", exception);
        }
    }

    private String serializeNullable(Object value) {
        return value == null ? null : serialize(value);
    }

    private String serialize(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JacksonException exception) {
            throw new IllegalArgumentException("cannot serialize verification evidence", exception);
        }
    }

    private static Long nullableLong(ResultSet rs, String column) throws SQLException {
        long value = rs.getLong(column);
        return rs.wasNull() ? null : value;
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : value.textValue();
    }

    private static Long boxedLong(JsonNode node, String field) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : value.longValue();
    }

    private static Integer boxedInt(JsonNode node, String field) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : value.intValue();
    }

    private static Instant instant(JsonNode node, String field) {
        String value = text(node, field);
        return value == null ? null : Instant.parse(value);
    }

    private static String bounded(String value, int limit) {
        if (value == null) return null;
        return value.length() <= limit ? value : value.substring(0, limit);
    }

    private static void requireOne(int changed, String operation) {
        if (changed != 1) throw new IllegalStateException(operation + " affected " + changed + " rows");
    }
}
