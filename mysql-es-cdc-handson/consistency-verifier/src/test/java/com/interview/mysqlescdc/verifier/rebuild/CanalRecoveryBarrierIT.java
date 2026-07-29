package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;

class CanalRecoveryBarrierIT {
    private JdbcClient jdbc;
    private CanalRecoveryBarrierService service;

    @BeforeEach void setUp(){var ds=new DriverManagerDataSource("jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true","root","rootpass");jdbc=JdbcClient.create(ds);cleanup();service=new CanalRecoveryBarrierService(jdbc,new JdbcBarrierPublisher(jdbc),new TransactionTemplate(new DataSourceTransactionManager(ds)));}
    @AfterEach void tearDown(){cleanup();}

    @Test void gate_owner_in_canal_recovering_can_publish_atomic_three_partition_marker(){UUID run=UUID.randomUUID(),marker=UUID.randomUUID();insertRun(run,"CANAL_RECOVERING");jdbc.sql("UPDATE product_write_gate SET closed=TRUE,owner_run_id=UUID_TO_BIN(:run),reason='recovery' WHERE singleton_id=1").param("run",run.toString()).update();Barrier barrier=service.publish(run,marker);assertThat(barrier.runId()).isEqualTo(marker);assertThat(barrier.partitionTokens()).containsExactlyInAnyOrder("0","1","2");assertThat(jdbc.sql("SELECT COUNT(*) FROM cdc_barrier WHERE run_id=UUID_TO_BIN(:run)").param("run",marker.toString()).query(Long.class).single()).isEqualTo(3);}
    @Test void wrong_phase_or_gate_owner_cannot_publish_any_marker(){UUID run=UUID.randomUUID(),marker=UUID.randomUUID();insertRun(run,"CANAL_RECOVERY_REQUIRED");assertThatThrownBy(()->service.publish(run,marker)).isInstanceOf(IllegalStateException.class);assertThat(jdbc.sql("SELECT COUNT(*) FROM cdc_barrier WHERE run_id=UUID_TO_BIN(:run)").param("run",marker.toString()).query(Long.class).single()).isZero();}

    private void insertRun(UUID run,String status){String stamp=DateTimeFormatter.ofPattern("yyyyMMddHHmmss").withZone(ZoneOffset.UTC).format(Instant.now());jdbc.sql("INSERT INTO rebuild_run(run_id,generation_name,status) VALUES(UUID_TO_BIN(:run),:name,:status)").param("run",run.toString()).param("name","products_v3_"+stamp+"_"+run.toString().substring(0,8)).param("status",status).update();}
    private void cleanup(){if(jdbc==null)return;jdbc.sql("DELETE FROM cdc_barrier").update();jdbc.sql("DELETE FROM canal_position_recovery").update();jdbc.sql("DELETE FROM rebuild_partition_offset").update();jdbc.sql("DELETE FROM rebuild_run").update();jdbc.sql("UPDATE product_write_gate SET closed=FALSE,owner_run_id=NULL,reason=NULL WHERE singleton_id=1").update();}
}
