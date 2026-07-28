package com.interview.mysqlescdc.verifier.rebuild;
import java.time.Duration;
import java.util.*;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.common.TopicPartition;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class AdminKafkaOffsetSnapshotter implements KafkaOffsetSnapshotter,AutoCloseable {
    private final Admin admin; private final JdbcClient jdbc; private final String configuredTopic;
    @Autowired public AdminKafkaOffsetSnapshotter(JdbcClient jdbc,@Value("${verification.kafka-bootstrap-servers:localhost:29092}") String servers,@Value("${verification.topic:product-search-revisions}") String topic){this(jdbc,Admin.create(Map.of(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG,servers)),topic);}
    AdminKafkaOffsetSnapshotter(JdbcClient jdbc,Admin admin,String configuredTopic){this.jdbc=jdbc;this.admin=admin;this.configuredTopic=configuredTopic;}
    public Map<TopicPartition,Long> endOffsets(String topic){requireTopic(topic);var result=offsets(topic,OffsetSpec.latest());requireExactPartitions(topic,result);return result;}
    public void assertRetained(String topic,Map<TopicPartition,Long> required){
        requireTopic(topic);Map<TopicPartition,Long> beginnings=offsets(topic,OffsetSpec.earliest()), ends=endOffsets(topic);requireExactPartitions(topic,beginnings);
        validateRequired(beginnings,ends,required);
    }
    static void validateRequired(Map<TopicPartition,Long> beginnings,Map<TopicPartition,Long> ends,Map<TopicPartition,Long> required){if(required==null||ends==null||beginnings==null||ends.isEmpty())throw new IllegalArgumentException("exactly configured three partitions required");String topic=ends.keySet().iterator().next().topic();Set<TopicPartition> exact=Set.of(new TopicPartition(topic,0),new TopicPartition(topic,1),new TopicPartition(topic,2));if(!ends.keySet().equals(exact)||!required.keySet().equals(exact)||!beginnings.keySet().equals(exact))throw new IllegalArgumentException("exactly configured three partitions required");required.forEach((partition,offset)->{if(offset==null||offset<0||offset>ends.get(partition))throw new IllegalArgumentException("invalid required offset");if(offset<beginnings.get(partition))throw new RequiredOffsetExpiredException(partition,offset,beginnings.get(partition));});}
    @Transactional public Map<TopicPartition,Long> captureAndPersist(UUID runId,String topic){Map<TopicPartition,Long> captured=endOffsets(topic);if(captured.size()!=3)throw new IllegalStateException("expected exactly three partitions");captured.forEach((partition,offset)->jdbc.sql("INSERT INTO rebuild_partition_offset(run_id,phase,topic_name,partition_id,next_offset) VALUES(UUID_TO_BIN(:run),'START',:topic,:partition,:offset)").param("run",runId.toString()).param("topic",topic).param("partition",partition.partition()).param("offset",offset).update());return captured;}
    private Map<TopicPartition,Long> offsets(String topic,OffsetSpec spec){try{var description=admin.describeTopics(List.of(topic)).allTopicNames().get().get(topic);Map<TopicPartition,OffsetSpec> request=new LinkedHashMap<>();description.partitions().forEach(info->request.put(new TopicPartition(topic,info.partition()),spec));var result=admin.listOffsets(request).all().get();Map<TopicPartition,Long> values=new LinkedHashMap<>();result.forEach((partition,info)->values.put(partition,info.offset()));return Map.copyOf(values);}catch(Exception e){throw new IllegalStateException("cannot read Kafka offsets",e);}}
    private void requireTopic(String topic){if(!configuredTopic.equals(topic))throw new IllegalArgumentException("configured topic required");}
    private static void requireExactPartitions(String topic,Map<TopicPartition,Long> offsets){if(!offsets.keySet().equals(Set.of(new TopicPartition(topic,0),new TopicPartition(topic,1),new TopicPartition(topic,2))))throw new IllegalStateException("exact partitions 0/1/2 required");}
    public void close(){admin.close(Duration.ofSeconds(5));}
}
