package com.interview.mysqlescdc.verifier.source;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Calendar;
import java.util.List;
import java.util.Optional;
import java.util.TimeZone;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public final class JdbcExpectedDocumentReader implements ExpectedDocumentReader {
    static final int MAX_PAGE_SIZE = 1_000;

    static final String SELECT_COLUMNS = """
            SELECT
              r.product_id AS expected_product_id,
              r.revision AS expected_revision,
              r.active AS expected_active,
              CASE WHEN r.active = 1 THEN p.sku END AS expected_sku,
              CASE WHEN r.active = 1 THEN p.name END AS expected_name,
              CASE WHEN r.active = 1 THEN p.description END AS expected_description,
              CASE WHEN r.active = 1 THEN p.category_id END AS expected_category_id,
              CASE WHEN r.active = 1 THEN c.name END AS expected_category_name,
              CASE WHEN r.active = 1 THEN p.price_cents END AS expected_price_cents,
              CASE WHEN r.active = 1 THEN i.available_quantity END AS expected_available_quantity,
              CASE WHEN r.active = 1
                THEN GREATEST(r.updated_at, p.updated_at, c.updated_at, i.updated_at)
                ELSE r.updated_at
              END AS expected_updated_at
            FROM product_search_revision r
            LEFT JOIN products p ON p.id = r.product_id
            LEFT JOIN categories c ON c.id = p.category_id
            LEFT JOIN inventory i ON i.product_id = r.product_id
            """;

    static final String PAGE_STATEMENT = SELECT_COLUMNS + """
            WHERE r.product_id > :exclusiveProductId
            ORDER BY r.product_id ASC
            LIMIT :queryLimit
            """;

    static final String LOAD_STATEMENT = SELECT_COLUMNS + """
            WHERE r.product_id = :productId
            """;

    private final JdbcClient jdbc;
    private final IndependentExpectedProjector projector;

    public JdbcExpectedDocumentReader(JdbcClient jdbc, IndependentExpectedProjector projector) {
        this.jdbc = jdbc;
        this.projector = projector;
    }

    @Override
    public ExpectedPage readAfter(long exclusiveProductId, int pageSize) {
        if (exclusiveProductId < 0) {
            throw new IllegalArgumentException("exclusiveProductId must be non-negative");
        }
        if (pageSize < 1 || pageSize > MAX_PAGE_SIZE) {
            throw new IllegalArgumentException("pageSize must be between 1 and " + MAX_PAGE_SIZE);
        }

        List<ExpectedDocument> queried = jdbc.sql(PAGE_STATEMENT)
                .param("exclusiveProductId", exclusiveProductId)
                .param("queryLimit", pageSize + 1)
                .query(this::mapDocument)
                .list();
        boolean complete = queried.size() <= pageSize;
        List<ExpectedDocument> documents = complete ? queried : queried.subList(0, pageSize);
        validateStrictOrder(documents, exclusiveProductId);
        long next = documents.isEmpty()
                ? exclusiveProductId
                : documents.getLast().productId();
        return new ExpectedPage(documents, next, complete);
    }

    @Override
    public Optional<ExpectedDocument> load(long productId) {
        if (productId < 1) {
            throw new IllegalArgumentException("positive productId required");
        }
        return jdbc.sql(LOAD_STATEMENT)
                .param("productId", productId)
                .query(this::mapDocument)
                .optional();
    }

    private ExpectedDocument mapDocument(ResultSet resultSet, int rowNumber) throws SQLException {
        long productId = requiredLong(resultSet, "expected_product_id", "revision identity");
        long revision = requiredLong(resultSet, "expected_revision", "revision identity");
        boolean active = resultSet.getBoolean("expected_active");
        if (resultSet.wasNull()) {
            throw incomplete(productId, "missing expected_active");
        }
        Instant updatedAt = requiredTimestamp(resultSet, "expected_updated_at", productId);
        if (!active) {
            return projector.project(ExpectedSourceRow.inactive(productId, revision, updatedAt));
        }

        try {
            return projector.project(new ExpectedSourceRow(
                    productId,
                    revision,
                    true,
                    resultSet.getString("expected_sku"),
                    resultSet.getString("expected_name"),
                    resultSet.getString("expected_description"),
                    nullableLong(resultSet, "expected_category_id"),
                    resultSet.getString("expected_category_name"),
                    nullableLong(resultSet, "expected_price_cents"),
                    nullableInt(resultSet, "expected_available_quantity"),
                    updatedAt));
        } catch (IllegalArgumentException | NullPointerException exception) {
            throw incomplete(productId, exception.getMessage(), exception);
        }
    }

    private static void validateStrictOrder(
            List<ExpectedDocument> documents, long exclusiveProductId) {
        long previous = exclusiveProductId;
        for (ExpectedDocument document : documents) {
            if (document.productId() <= previous) {
                throw new IllegalStateException(
                        "source page is not strictly ordered after product " + previous);
            }
            previous = document.productId();
        }
    }

    private static long requiredLong(ResultSet resultSet, String column, String context)
            throws SQLException {
        long value = resultSet.getLong(column);
        if (resultSet.wasNull()) {
            throw new IllegalStateException("missing " + column + " in " + context);
        }
        return value;
    }

    private static Long nullableLong(ResultSet resultSet, String column) throws SQLException {
        long value = resultSet.getLong(column);
        return resultSet.wasNull() ? null : value;
    }

    private static Integer nullableInt(ResultSet resultSet, String column) throws SQLException {
        int value = resultSet.getInt(column);
        return resultSet.wasNull() ? null : value;
    }

    private static Instant requiredTimestamp(ResultSet resultSet, String column, long productId)
            throws SQLException {
        Calendar utc = Calendar.getInstance(TimeZone.getTimeZone("UTC"));
        Timestamp timestamp = resultSet.getTimestamp(column, utc);
        if (timestamp == null) {
            throw incomplete(productId, "missing " + column);
        }
        return timestamp.toInstant();
    }

    private static IllegalStateException incomplete(long productId, String detail) {
        return new IllegalStateException(
                "incomplete active expected source row for product " + productId + ": " + detail);
    }

    private static IllegalStateException incomplete(
            long productId, String detail, RuntimeException cause) {
        return new IllegalStateException(
                "incomplete active expected source row for product " + productId + ": " + detail,
                cause);
    }
}
