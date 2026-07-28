package com.interview.mysqlescdc.consumer.source;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class JdbcSourceSnapshotRepository implements SourceSnapshotRepository {
    static final String SELECT_STATEMENT = """
            SELECT
              r.product_id,
              r.revision,
              r.active,
              p.sku,
              p.name,
              p.description,
              p.category_id,
              c.name AS category_name,
              p.price_cents,
              i.available_quantity,
              GREATEST(r.updated_at, p.updated_at, c.updated_at, i.updated_at)
                AS source_updated_at
            FROM product_search_revision r
            LEFT JOIN products p ON p.id = r.product_id
            LEFT JOIN categories c ON c.id = p.category_id
            LEFT JOIN inventory i ON i.product_id = p.id
            WHERE r.product_id = :productId
            """;

    private final JdbcClient jdbc;

    public JdbcSourceSnapshotRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public Optional<SourceProductSnapshot> load(long productId) {
        if (productId < 1) {
            throw new IllegalArgumentException("positive productId required");
        }
        return jdbc.sql(SELECT_STATEMENT)
                .param("productId", productId)
                .query(this::mapSnapshot)
                .optional();
    }

    private SourceProductSnapshot mapSnapshot(ResultSet resultSet, int rowNumber) throws SQLException {
        long productId = resultSet.getLong("product_id");
        long revision = resultSet.getLong("revision");
        boolean active = resultSet.getBoolean("active");
        if (!active) {
            Timestamp revisionUpdatedAt = requireTimestamp(
                    resultSet, "source_updated_at", productId, false);
            return SourceProductSnapshot.inactive(
                    productId, revision, revisionUpdatedAt.toInstant());
        }

        try {
            return SourceProductSnapshot.active(
                    productId,
                    requireString(resultSet, "sku"),
                    requireString(resultSet, "name"),
                    requireString(resultSet, "description"),
                    requireLong(resultSet, "category_id"),
                    requireString(resultSet, "category_name"),
                    requireLong(resultSet, "price_cents"),
                    requireInt(resultSet, "available_quantity"),
                    revision,
                    requireTimestamp(resultSet, "source_updated_at", productId, true).toInstant());
        } catch (IllegalStateException exception) {
            throw new IllegalStateException(
                    "incomplete active source snapshot for product " + productId,
                    exception);
        }
    }

    private static String requireString(ResultSet resultSet, String column) throws SQLException {
        String value = resultSet.getString(column);
        if (value == null) {
            throw new IllegalStateException("missing " + column);
        }
        return value;
    }

    private static long requireLong(ResultSet resultSet, String column) throws SQLException {
        long value = resultSet.getLong(column);
        if (resultSet.wasNull()) {
            throw new IllegalStateException("missing " + column);
        }
        return value;
    }

    private static int requireInt(ResultSet resultSet, String column) throws SQLException {
        int value = resultSet.getInt(column);
        if (resultSet.wasNull()) {
            throw new IllegalStateException("missing " + column);
        }
        return value;
    }

    private static Timestamp requireTimestamp(
            ResultSet resultSet, String column, long productId, boolean active) throws SQLException {
        Timestamp value = resultSet.getTimestamp(column);
        if (value == null) {
            String state = active ? "active" : "inactive";
            throw new IllegalStateException(
                    "incomplete " + state + " source snapshot for product " + productId
                            + ": missing " + column);
        }
        return value;
    }
}
