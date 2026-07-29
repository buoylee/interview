package com.interview.mysqlescdc.verifier.rebuild;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.function.Supplier;
import javax.sql.DataSource;
import org.springframework.stereotype.Component;

@Component
public final class RebuildAdvisoryLock {
    private static final String NAME = "mysql-es-cdc-rebuild";
    private final DataSource source;

    public RebuildAdvisoryLock(DataSource source) { this.source = source; }

    public <T> T execute(Supplier<T> work) {
        try (Connection connection = source.getConnection()) {
            connection.setAutoCommit(true);
            long connectionId = scalar(connection, "SELECT CONNECTION_ID()", false);
            if (scalar(connection, "SELECT GET_LOCK(?,0)", true) != 1) {
                throw new IllegalStateException("rebuild advisory lock busy");
            }
            RuntimeException primary = null;
            try {
                requireOwner(connection, connectionId);
                T result = work.get();
                requireOwner(connection, connectionId);
                return result;
            } catch (RuntimeException failure) {
                primary = failure;
                try { requireOwner(connection, connectionId); }
                catch (RuntimeException uncertainty) { failure.addSuppressed(uncertainty); }
                throw failure;
            } finally {
                try {
                    if (connection.isClosed() || scalar(connection,"SELECT RELEASE_LOCK(?)",true) != 1) {
                        throw new IllegalStateException("rebuild advisory lock release uncertain");
                    }
                } catch (SQLException | RuntimeException releaseFailure) {
                    if (primary != null) primary.addSuppressed(releaseFailure);
                    else if (releaseFailure instanceof RuntimeException runtime) throw runtime;
                    else throw new IllegalStateException("rebuild advisory lock lost", releaseFailure);
                }
            }
        } catch (SQLException failure) {
            throw new IllegalStateException("rebuild advisory lock lost", failure);
        }
    }

    private void requireOwner(Connection connection, long expectedConnectionId) {
        try {
            if (connection.isClosed()
                    || scalar(connection,"SELECT IS_USED_LOCK(?)",true) != expectedConnectionId) {
                throw new IllegalStateException("rebuild advisory lock uncertain");
            }
        } catch (SQLException failure) {
            throw new IllegalStateException("rebuild advisory lock uncertain", failure);
        }
    }

    private long scalar(Connection connection, String sql, boolean bindName) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            if (bindName) statement.setString(1, NAME);
            try (ResultSet result = statement.executeQuery()) {
                if (!result.next()) throw new SQLException("missing lock result");
                long value = result.getLong(1);
                if (result.wasNull()) throw new SQLException("null lock result");
                return value;
            }
        }
    }
}
