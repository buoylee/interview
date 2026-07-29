package com.interview.mysqlescdc.verifier.lab;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.util.List;
import java.util.Properties;
import java.util.UUID;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.Test;

class ScenarioEventProducerIT {
    private static final String PAYLOAD = "{\"id\":91,\"database\":\"product_catalog\",\"table\":\"product_search_revision\",\"isDdl\":false,\"type\":\"UPDATE\",\"data\":[{\"product_id\":\"1001\",\"revision\":\"1\",\"active\":\"1\"}]}";

    @Test void sends_to_exact_partition_with_null_key_and_returns_broker_offset() {
        var producer = new ScenarioEventProducer("localhost:29092", true);
        var ack = producer.send(new ScenarioEventRequest("product-search-revisions", 1, PAYLOAD));
        assertThat(ack.partition()).isEqualTo(1);
        try (var consumer = new KafkaConsumer<String,String>(consumerProperties())) {
            var tp = new TopicPartition("product-search-revisions",1);consumer.assign(List.of(tp));consumer.seek(tp,ack.offset());
            var record=consumer.poll(Duration.ofSeconds(5)).records(tp).iterator().next();
            assertThat(record.key()).isNull();assertThat(record.value()).isEqualTo(PAYLOAD);assertThat(record.offset()).isEqualTo(ack.offset());
        }
    }

    @Test void rejects_invalid_requests_before_sender_creation() {
        var producer = new ScenarioEventProducer("localhost:1", true);
        assertThatThrownBy(()->producer.send(new ScenarioEventRequest("wrong",1,PAYLOAD))).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(()->producer.send(new ScenarioEventRequest("product-search-revisions",3,PAYLOAD))).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(()->producer.send(new ScenarioEventRequest("product-search-revisions",1,"{}"))).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(()->new ScenarioEventProducer("localhost:1",false).send(new ScenarioEventRequest("product-search-revisions",1,PAYLOAD))).isInstanceOf(IllegalStateException.class);
    }

    @Test void rejects_non_integral_nested_extra_and_out_of_range_flat_rows_before_sender_creation() {
        var producer = new ScenarioEventProducer("localhost:1", true);
        var invalidRows = List.of(
                "{\"product_id\":1,\"revision\":1,\"active\":1,\"extra\":0}",
                "{\"product_id\":true,\"revision\":1,\"active\":1}",
                "{\"product_id\":1.5,\"revision\":1,\"active\":1}",
                "{\"product_id\":0,\"revision\":1,\"active\":1}",
                "{\"product_id\":1,\"revision\":0,\"active\":1}",
                "{\"product_id\":1,\"revision\":1,\"active\":2}",
                "{\"product_id\":1,\"revision\":1,\"active\":false}",
                "{\"product_id\":{},\"revision\":1,\"active\":1}");
        for (var row : invalidRows) {
            var payload = "{\"database\":\"product_catalog\",\"table\":\"product_search_revision\",\"isDdl\":false,\"type\":\"UPDATE\",\"data\":[" + row + "]}";
            assertThatThrownBy(() -> producer.send(new ScenarioEventRequest("product-search-revisions", 1, payload)))
                    .as(row).isInstanceOf(IllegalArgumentException.class);
        }
        var row = "{\"product_id\":1,\"revision\":1,\"active\":1}";
        var tooMany = "{\"database\":\"product_catalog\",\"table\":\"product_search_revision\",\"isDdl\":false,\"type\":\"UPDATE\",\"data\":[" +
                String.join(",", java.util.Collections.nCopies(1001, row)) + "]}";
        assertThatThrownBy(() -> producer.send(new ScenarioEventRequest("product-search-revisions", 1, tooMany)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private static Properties consumerProperties(){var p=new Properties();p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,"localhost:29092");p.put(ConsumerConfig.GROUP_ID_CONFIG,"m6-injection-it-"+ UUID.randomUUID());p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,"false");p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"none");p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);return p;}
}
