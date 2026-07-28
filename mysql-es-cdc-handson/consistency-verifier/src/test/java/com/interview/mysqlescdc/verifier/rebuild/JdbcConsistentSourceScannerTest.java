package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.clearInvocations;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.sql.Connection;
import java.sql.Statement;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;
import com.interview.mysqlescdc.verifier.source.IndependentExpectedProjector;

class JdbcConsistentSourceScannerTest {

    @Test
    void close_rolls_back_before_connection_close_and_is_idempotent() throws Exception {
        DataSource source = mock(DataSource.class);
        Connection connection = mock(Connection.class);
        Statement statement = mock(Statement.class);
        when(source.getConnection()).thenReturn(connection);
        when(connection.createStatement()).thenReturn(statement);

        SourceSnapshotCursor cursor = new JdbcConsistentSourceScanner(
                source, new IndependentExpectedProjector()).open();
        clearInvocations(connection);

        cursor.close();
        cursor.close();

        var order = inOrder(connection);
        order.verify(connection).rollback();
        order.verify(connection).close();
        verify(connection, times(1)).rollback();
        verify(connection, times(1)).close();
    }

    @Test
    void close_surfaces_rollback_and_connection_close_failures() throws Exception {
        DataSource source = mock(DataSource.class);
        Connection connection = mock(Connection.class);
        Statement statement = mock(Statement.class);
        when(source.getConnection()).thenReturn(connection);
        when(connection.createStatement()).thenReturn(statement);
        org.mockito.Mockito.doThrow(new java.sql.SQLException("rollback boom"))
                .when(connection).rollback();
        org.mockito.Mockito.doThrow(new java.sql.SQLException("close boom"))
                .when(connection).close();

        SourceSnapshotCursor cursor = new JdbcConsistentSourceScanner(
                source, new IndependentExpectedProjector()).open();

        assertThatThrownBy(cursor::close)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("rollback failed")
                .satisfies(error -> assertThat(error.getSuppressed())
                        .singleElement()
                        .extracting(Throwable::getMessage)
                        .isEqualTo("snapshot connection close failed"));
    }

    @Test
    void opening_failure_closes_physical_connection_and_releases_permit() throws Exception {
        DataSource source = mock(DataSource.class);
        Connection broken = mock(Connection.class);
        when(source.getConnection()).thenReturn(broken);
        when(broken.createStatement()).thenThrow(new java.sql.SQLException("start failed"));
        JdbcConsistentSourceScanner scanner = new JdbcConsistentSourceScanner(
                source, new IndependentExpectedProjector());

        for (int attempt = 0; attempt < 5; attempt++) {
            assertThatThrownBy(scanner::open)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("cannot open");
        }

        verify(source, times(5)).getConnection();
        verify(broken, times(5)).close();
    }
}
