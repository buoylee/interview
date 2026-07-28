package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.*;
import java.util.*;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.clients.admin.*;
import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

class AdminKafkaOffsetSnapshotterIT {
    static final String TOPIC="product-search-revisions"; AdminKafkaOffsetSnapshotter snapshotter; JdbcClient jdbc,root; TransactionTemplate tx;
    final List<UUID> runs=new ArrayList<>();
    @BeforeEach void setup(){var ds=new DriverManagerDataSource("jdbc:mysql://127.0.0.1:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true","verifier","verifierpass");jdbc=JdbcClient.create(ds);root=JdbcClient.create(new DriverManagerDataSource("jdbc:mysql://127.0.0.1:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true","root","rootpass"));tx=new TransactionTemplate(new DataSourceTransactionManager(ds));snapshotter=new AdminKafkaOffsetSnapshotter(jdbc,Admin.create(Map.of(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG,"127.0.0.1:29092")),TOPIC);}
    @AfterEach void cleanup(){for(var run:runs){root.sql("DELETE FROM rebuild_partition_offset WHERE run_id=UUID_TO_BIN(:run)").param("run",run.toString()).update();root.sql("DELETE FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)").param("run",run.toString()).update();}snapshotter.close();}
    @Test void captures_exact_real_end_offsets_and_returns_only_after_all_three_start_rows_are_durable(){UUID run=createRun();Map<TopicPartition,Long> captured=tx.execute(s->snapshotter.captureAndPersist(run,TOPIC));assertThat(captured.keySet()).containsExactlyInAnyOrder(new TopicPartition(TOPIC,0),new TopicPartition(TOPIC,1),new TopicPartition(TOPIC,2));assertThat(read(run)).containsExactlyEntriesOf(Map.of(0,captured.get(new TopicPartition(TOPIC,0)),1,captured.get(new TopicPartition(TOPIC,1)),2,captured.get(new TopicPartition(TOPIC,2))));}
    @Test void late_collision_rolls_back_first_two_inserts_atomically(){UUID run=createRun();jdbc.sql("INSERT INTO rebuild_partition_offset(run_id,phase,topic_name,partition_id,next_offset) VALUES(UUID_TO_BIN(:run),'START',:topic,2,0)").param("run",run.toString()).param("topic",TOPIC).update();assertThatThrownBy(()->tx.executeWithoutResult(s->snapshotter.captureAndPersist(run,TOPIC))).isInstanceOf(RuntimeException.class);assertThat(read(run)).containsExactlyEntriesOf(Map.of(2,0L));}
    @Test void rejects_non_configured_topic(){assertThatThrownBy(()->snapshotter.endOffsets("other-topic")).isInstanceOf(IllegalArgumentException.class);}
    private UUID createRun(){UUID run=UUID.randomUUID();runs.add(run);jdbc.sql("INSERT INTO rebuild_run(run_id,generation_name,status) VALUES(UUID_TO_BIN(:run),:name,'CREATED')").param("run",run.toString()).param("name","products_v3_20260728123456_"+run.toString().substring(0,8)).update();return run;}
    private Map<Integer,Long> read(UUID run){return jdbc.sql("SELECT partition_id,next_offset FROM rebuild_partition_offset WHERE run_id=UUID_TO_BIN(:run) AND phase='START'").param("run",run.toString()).query((rs,n)->Map.entry(rs.getInt(1),rs.getLong(2))).list().stream().collect(java.util.stream.Collectors.toMap(Map.Entry::getKey,Map.Entry::getValue));}
}
