package com.interview.mysqlescdc.consumer.rebuild;
import java.util.*;import org.apache.kafka.clients.consumer.*;import org.apache.kafka.common.serialization.StringDeserializer;import org.springframework.beans.factory.annotation.Value;import org.springframework.stereotype.Component;
@Component public final class KafkaShadowConsumerFactory implements ShadowConsumerFactory {
 private final String bootstrap; public KafkaShadowConsumerFactory(@Value("${spring.kafka.bootstrap-servers}")String bootstrap){this.bootstrap=bootstrap;}
 public Consumer<String,String> create(UUID runId){return new KafkaConsumer<>(properties(bootstrap,runId));}
 static Properties properties(String bootstrap,UUID runId){var p=new Properties();p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,"false");p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"none");p.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG,"read_committed");p.put(ConsumerConfig.GROUP_ID_CONFIG,"rebuild-shadow-"+runId);return p;}
}
