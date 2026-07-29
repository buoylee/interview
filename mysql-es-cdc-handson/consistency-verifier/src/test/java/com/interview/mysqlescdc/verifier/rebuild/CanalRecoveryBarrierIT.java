package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.UUID;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

@SpringBootTest
class CanalRecoveryBarrierIT {
    @Autowired CanalRecoveryBarrierService service;
    @Autowired CanalRecoveryService recoveryService;
    JdbcClient root;

    @BeforeEach void setUp() {
        root=JdbcClient.create(new DriverManagerDataSource("jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true","root","rootpass"));
        root.sql("DELETE FROM canal_recovery_observation").update();
        root.sql("DELETE FROM cdc_barrier").update();
        root.sql("DELETE FROM canal_position_recovery").update();
        root.sql("DELETE FROM rebuild_partition_offset").update();
        root.sql("DELETE FROM rebuild_run").update();
        root.sql("UPDATE product_write_gate SET closed=FALSE,owner_run_id=NULL,reason=NULL WHERE singleton_id=1").update();
    }
    @AfterEach void tearDown(){setUp();}

    @Test void verifier_publishes_observes_and_persists_actual_raw_records() {
        UUID run=UUID.randomUUID(),marker=UUID.randomUUID();insertRun(run,"CANAL_RECOVERING");ownGate(run);
        Map<Integer,Long> before=endOffsets();
        RecoveryBarrierObservation observed=service.publishAndObserve(run,marker,"RESET_ANCHOR",before);
        assertThat(observed.markerRunId()).isEqualTo(marker);
        assertThat(observed.events()).allSatisfy(event -> {
            assertThat(event.runId()).isEqualTo(marker);
            assertThat(event.nextOffset()).isEqualTo(before.get(event.partition())+1);
        });
        assertThat(root.sql("SELECT COUNT(*) FROM canal_recovery_observation WHERE rebuild_run_id=UUID_TO_BIN(:run) AND kind='RESET_ANCHOR'")
                .param("run",run.toString()).query(Long.class).single()).isEqualTo(1);
        recoveryService.requireObserved(run,"RESET_ANCHOR",marker,observed.offsets(),observed.events());
        assertThatThrownBy(() -> recoveryService.requireObserved(run,"RESET_ANCHOR",marker,
                Map.of(0,observed.offsets().get(0),1,observed.offsets().get(1),2,observed.offsets().get(2)+1),observed.events()))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> recoveryService.requireObserved(run,"RESET_ANCHOR",UUID.randomUUID(),
                observed.offsets(),observed.events())).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> service.publishAndObserve(run,UUID.randomUUID(),"RESET_ANCHOR",endOffsets()))
                .isInstanceOf(RuntimeException.class);
    }

    @Test void wrong_phase_cannot_publish_or_observe() {
        UUID run=UUID.randomUUID(),marker=UUID.randomUUID();insertRun(run,"CANAL_RECOVERY_REQUIRED");
        assertThatThrownBy(() -> service.publishAndObserve(run,marker,"NORMAL_SENTINEL",endOffsets()))
                .isInstanceOf(IllegalStateException.class);
        assertThat(root.sql("SELECT COUNT(*) FROM cdc_barrier WHERE run_id=UUID_TO_BIN(:run)")
                .param("run",marker.toString()).query(Long.class).single()).isZero();
    }

    private void ownGate(UUID run){root.sql("UPDATE product_write_gate SET closed=TRUE,owner_run_id=UUID_TO_BIN(:run),reason='recovery' WHERE singleton_id=1").param("run",run.toString()).update();}
    private void insertRun(UUID run,String status){String stamp=DateTimeFormatter.ofPattern("yyyyMMddHHmmss").withZone(ZoneOffset.UTC).format(Instant.now());root.sql("INSERT INTO rebuild_run(run_id,generation_name,status) VALUES(UUID_TO_BIN(:run),:name,:status)").param("run",run.toString()).param("name","products_v3_"+stamp+"_"+run.toString().substring(0,8)).param("status",status).update();}
    private static Map<Integer,Long> endOffsets(){List<TopicPartition> p=List.of(new TopicPartition("product-search-revisions",0),new TopicPartition("product-search-revisions",1),new TopicPartition("product-search-revisions",2));try(var c=new KafkaConsumer<String,String>(props())){var ends=c.endOffsets(p);return Map.of(0,ends.get(p.get(0)),1,ends.get(p.get(1)),2,ends.get(p.get(2)));}}
    private static Properties props(){Properties p=new Properties();p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,"127.0.0.1:29092");p.put(ConsumerConfig.GROUP_ID_CONFIG,"recovery-it-"+UUID.randomUUID());p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,"false");p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);return p;}
}
