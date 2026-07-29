package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

class JdbcRebuildRunStoreIT {
    private JdbcClient root;
    private JdbcRebuildRunStore store;

    @BeforeEach void setUp() {
        root = JdbcClient.create(new DriverManagerDataSource(
                "jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true",
                "root", "rootpass"));
        cleanup();
        store = new JdbcRebuildRunStore(root);
    }

    @AfterEach void tearDown() { cleanup(); }

    @Test void real_mysql_enforces_one_nonterminal_run_and_current_state_cas() {
        UUID first = UUID.randomUUID(), second = UUID.randomUUID();
        store.create(new RebuildRequest(first,"MANUAL","product-search-revisions",200));
        assertThatThrownBy(() -> store.create(new RebuildRequest(second,"MANUAL","product-search-revisions",200)))
                .hasMessageContaining("one nonterminal");
        store.transition(first,"CREATED","SNAPSHOTTING");
        assertThatThrownBy(() -> store.transition(first,"CREATED","REPLAYING"))
                .hasMessageContaining("transition lost");
        assertThat(store.get(first).status()).isEqualTo("SNAPSHOTTING");
    }

    private void cleanup() {
        if (root == null) return;
        root.sql("DELETE FROM canal_position_recovery").update();
        root.sql("DELETE FROM rebuild_partition_offset").update();
        root.sql("DELETE FROM rebuild_run").update();
        root.sql("UPDATE pipeline_condition SET active=FALSE,cleared_at=CURRENT_TIMESTAMP(6) WHERE condition_key='REBUILD_IN_PROGRESS'").update();
    }
}
