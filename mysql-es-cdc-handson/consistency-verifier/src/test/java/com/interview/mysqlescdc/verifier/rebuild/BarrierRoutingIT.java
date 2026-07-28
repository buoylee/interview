package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import java.util.UUID;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.HashMap;
import javax.sql.DataSource;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;

class BarrierRoutingIT {
    JdbcClient jdbc;
    JdbcBarrierPublisher publisher;
    TransactionTemplate transactions;
    @BeforeEach void setUp() {
        DataSource ds = new DriverManagerDataSource("jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true", "verifier", "verifierpass");
        jdbc = JdbcClient.create(ds);
        publisher = new JdbcBarrierPublisher(jdbc);
        transactions = new TransactionTemplate(new DataSourceTransactionManager(ds));
        JdbcClient.create(new DriverManagerDataSource("jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true", "root", "rootpass"))
                .sql("DELETE FROM cdc_barrier").update();
    }
    @Test void real_canal_routes_one_null_key_marker_to_each_partition_at_exact_offsets() {
        List<TopicPartition> partitions = List.of(new TopicPartition("product-search-revisions",0), new TopicPartition("product-search-revisions",1), new TopicPartition("product-search-revisions",2));
        try (KafkaConsumer<String,String> consumer = new KafkaConsumer<>(consumerProperties())) {
            consumer.assign(partitions);
            Map<TopicPartition,Long> baseline = consumer.endOffsets(partitions);
            baseline.forEach(consumer::seek);
            UUID run = UUID.randomUUID();
            transactions.executeWithoutResult(status -> publisher.publish(run,3));
            Map<Integer,String> tokens = new HashMap<>();
            Map<Integer,Long> offsets = new HashMap<>();
            String encodedRun = null;
            Instant deadline=Instant.now().plusSeconds(45);
            JsonMapper json=JsonMapper.builder().build();
            while (tokens.size()<3 && Instant.now().isBefore(deadline)) {
                for (var record: consumer.poll(Duration.ofMillis(500))) {
                    var root=json.readTree(record.value());
                    if (!"cdc_barrier".equals(root.path("table").asText())) continue;
                    for (var row: root.path("data")) {
                        String token=row.path("partition_token").asText();
                        if (!token.equals(Integer.toString(record.partition()))) continue;
                        assertThat(record.key()).isNull();
                        assertThat(record.offset()).isEqualTo(baseline.get(new TopicPartition(record.topic(),record.partition())));
                        String currentRun=row.path("run_id").asText();
                        if (encodedRun==null) encodedRun=currentRun; else assertThat(currentRun).isEqualTo(encodedRun);
                        assertThat(tokens.put(record.partition(),token)).isNull();
                        offsets.put(record.partition(),record.offset());
                    }
                }
            }
            assertThat(tokens).containsExactlyInAnyOrderEntriesOf(Map.of(0,"0",1,"1",2,"2"));
            assertThat(offsets).hasSize(3);
        } catch (Exception exception) { throw new AssertionError(exception); }
    }
    @Test void publishes_exactly_three_tokens_and_duplicate_is_atomic() {
        UUID run = UUID.randomUUID();
        assertThat(publisher.publish(run,3).partitionTokens()).containsExactlyInAnyOrder("0","1","2");
        assertThat(jdbc.sql("SELECT partition_token FROM cdc_barrier WHERE run_id=UUID_TO_BIN(:run) ORDER BY partition_token")
                .param("run",run.toString()).query(String.class).list()).containsExactly("0","1","2");
        assertThatThrownBy(() -> publisher.publish(run,3)).isInstanceOf(RuntimeException.class);
        assertThat(jdbc.sql("SELECT COUNT(*) FROM cdc_barrier WHERE run_id=UUID_TO_BIN(:run)").param("run",run.toString()).query(Long.class).single()).isEqualTo(3);
    }
    @Test void rejects_any_partition_count_other_than_three() {
        assertThatThrownBy(() -> publisher.publish(UUID.randomUUID(),2)).isInstanceOf(IllegalArgumentException.class);
    }
    private static Properties consumerProperties() {
        Properties p=new Properties();
        p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,"127.0.0.1:29092");
        p.put(ConsumerConfig.GROUP_ID_CONFIG,"barrier-routing-"+UUID.randomUUID());
        p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,"false");
        p.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG,"read_committed");
        p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);
        p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);
        return p;
    }
}
