package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import java.util.UUID;
import java.sql.Connection;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.TransactionTemplate;

class JdbcWriteGateIT {
    DataSource verifier;
    JdbcClient root;
    JdbcWriteGate gate;
    @BeforeEach void setUp() {
        verifier = new DriverManagerDataSource("jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true", "verifier", "verifierpass");
        root = JdbcClient.create(new DriverManagerDataSource("jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true", "root", "rootpass"));
        root.sql("UPDATE product_write_gate SET closed=FALSE,owner_run_id=NULL,reason=NULL WHERE singleton_id=1").update();
        gate = new JdbcWriteGate(JdbcClient.create(verifier), new TransactionTemplate(new DataSourceTransactionManager(verifier)));
    }
    @Test void exclusive_close_waits_until_an_independent_shared_lock_commits() throws Exception {
        UUID owner = UUID.randomUUID();
        CountDownLatch sharedHeld = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            var mutation = executor.submit(() -> {
                try (Connection connection = verifier.getConnection()) {
                    connection.setAutoCommit(false);
                    try (var statement = connection.prepareStatement(
                            "SELECT closed FROM product_write_gate WHERE singleton_id=1 FOR SHARE")) {
                        statement.executeQuery().next();
                        sharedHeld.countDown();
                        release.await(5, TimeUnit.SECONDS);
                        connection.commit();
                    }
                }
                return null;
            });
            assertThat(sharedHeld.await(2, TimeUnit.SECONDS)).isTrue();
            var closing = executor.submit(() -> gate.close(owner, "cutover"));
            Thread.sleep(200);
            assertThat(closing.isDone()).isFalse();
            release.countDown();
            mutation.get(3, TimeUnit.SECONDS);
            assertThat(closing.get(3, TimeUnit.SECONDS).runId()).isEqualTo(owner);
        }
    }
    @Test void ownership_is_exact_and_same_owner_operations_are_idempotent() {
        UUID owner=UUID.randomUUID(), other=UUID.randomUUID();
        gate.close(owner,"cutover"); gate.close(owner,"cutover");
        assertThatThrownBy(() -> gate.close(other,"steal")).isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> gate.open(other)).isInstanceOf(IllegalStateException.class);
        gate.open(owner); gate.open(owner);
        assertThat(root.sql("SELECT closed FROM product_write_gate WHERE singleton_id=1").query(Boolean.class).single()).isFalse();
    }
}
