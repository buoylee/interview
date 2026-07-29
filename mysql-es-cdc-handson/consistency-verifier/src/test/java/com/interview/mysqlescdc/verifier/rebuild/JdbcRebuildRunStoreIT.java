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
        store.create(new RebuildRequest(first,"NORMAL","product-search-revisions",200));
        assertThatThrownBy(() -> store.create(new RebuildRequest(second,"NORMAL","product-search-revisions",200)))
                .hasMessageContaining("one nonterminal");
        store.transition(first,"CREATED","SNAPSHOTTING");
        assertThatThrownBy(() -> store.transition(first,"CREATED","REPLAYING"))
                .hasMessageContaining("transition lost");
        assertThat(store.get(first).status()).isEqualTo("SNAPSHOTTING");
    }

    @Test void rebuild_creation_claims_only_the_condition_types_covered_by_its_reason() {
        UUID normal = UUID.randomUUID();
        activate("LOG_GAP");
        activate("REBUILD_REQUIRED");

        store.create(new RebuildRequest(normal,"NORMAL","product-search-revisions",200));

        assertThat(owner("REBUILD_REQUIRED")).isEqualTo(normal.toString());
        assertThat(owner("LOG_GAP")).isNull();
        assertThat(root.sql("SELECT rebuild_reason FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)")
                .param("run", normal.toString()).query(String.class).single()).isEqualTo("NORMAL");
    }

    private void activate(String condition) {
        root.sql("""
                INSERT INTO pipeline_condition(condition_key,active,details_json,observed_at,cleared_at,owner_rebuild_run_id)
                VALUES(:condition,TRUE,JSON_OBJECT(),CURRENT_TIMESTAMP(6),NULL,NULL)
                ON DUPLICATE KEY UPDATE active=TRUE,owner_rebuild_run_id=NULL,cleared_at=NULL
                """).param("condition", condition).update();
    }

    private String owner(String condition) {
        return root.sql("SELECT BIN_TO_UUID(owner_rebuild_run_id) FROM pipeline_condition WHERE condition_key=:condition")
                .param("condition", condition).query(String.class).optional().orElse(null);
    }

    private void cleanup() {
        if (root == null) return;
        root.sql("DELETE FROM canal_position_recovery").update();
        root.sql("DELETE FROM rebuild_partition_offset").update();
        root.sql("DELETE FROM rebuild_run").update();
        root.sql("UPDATE pipeline_condition SET active=FALSE,owner_rebuild_run_id=NULL,cleared_at=CURRENT_TIMESTAMP(6) WHERE condition_key IN ('REBUILD_IN_PROGRESS','LOG_GAP','REBUILD_REQUIRED')").update();
    }
}
