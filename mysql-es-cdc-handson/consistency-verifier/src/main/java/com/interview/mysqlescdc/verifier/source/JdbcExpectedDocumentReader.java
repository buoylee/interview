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

    static final String REVISION_STATE = """
            SELECT
              r.product_id AS state_product_id,
              r.revision AS state_revision,
              TRUE AS state_active,
              facts.sku AS state_sku,
              facts.product_name AS state_name,
              facts.description AS state_description,
              facts.category_id AS state_category_id,
              facts.category_name AS state_category_name,
              facts.price_cents AS state_price_cents,
              facts.available_quantity AS state_available_quantity,
              CASE WHEN facts.fact_product_id IS NULL THEN 0 ELSE 1 END AS state_complete,
              CASE WHEN facts.fact_product_id IS NULL THEN r.updated_at
                   ELSE GREATEST(r.updated_at, facts.product_updated_at,
                         facts.category_updated_at, facts.inventory_updated_at)
              END AS state_updated_at
            FROM product_search_revision r
            LEFT JOIN (
              SELECT
                p.id AS fact_product_id,
                p.sku,
                p.name AS product_name,
                p.description,
                p.category_id,
                c.name AS category_name,
                p.price_cents,
                i.available_quantity,
                p.updated_at AS product_updated_at,
                c.updated_at AS category_updated_at,
                i.updated_at AS inventory_updated_at
              FROM products p
              INNER JOIN categories c ON c.id = p.category_id
              INNER JOIN inventory i ON i.product_id = p.id
            ) facts ON facts.fact_product_id = r.product_id
            WHERE r.active = TRUE

            UNION ALL

            SELECT
              r.product_id AS state_product_id,
              r.revision AS state_revision,
              FALSE AS state_active,
              CAST(NULL AS CHAR) AS state_sku,
              CAST(NULL AS CHAR) AS state_name,
              CAST(NULL AS CHAR) AS state_description,
              CAST(NULL AS SIGNED) AS state_category_id,
              CAST(NULL AS CHAR) AS state_category_name,
              CAST(NULL AS SIGNED) AS state_price_cents,
              CAST(NULL AS SIGNED) AS state_available_quantity,
              1 AS state_complete,
              r.updated_at AS state_updated_at
            FROM product_search_revision r
            WHERE r.active = FALSE
            """;

    static final String SELECT_FROM_REVISION_STATE = """
            SELECT
              state_product_id AS expected_product_id,
              state_revision AS expected_revision,
              state_active AS expected_active,
              state_sku AS expected_sku,
              state_name AS expected_name,
              state_description AS expected_description,
              state_category_id AS expected_category_id,
              state_category_name AS expected_category_name,
              state_price_cents AS expected_price_cents,
              state_available_quantity AS expected_available_quantity,
              state_complete AS expected_complete,
              state_updated_at AS expected_updated_at
            FROM (
            """ + REVISION_STATE + """
            ) revision_state
            """;

    static final String PAGE_STATEMENT = SELECT_FROM_REVISION_STATE + """
            WHERE state_product_id > :exclusiveProductId
            ORDER BY state_product_id ASC
            LIMIT :queryLimit
            """;

    static final String LOAD_STATEMENT = SELECT_FROM_REVISION_STATE + """
            WHERE state_product_id = :productId
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
        boolean complete = resultSet.getBoolean("expected_complete");
        if (resultSet.wasNull() || !complete) {
            throw incomplete(productId, "business aggregate is absent");
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
