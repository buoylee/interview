package com.interview.mysqlescdc.verifier.rebuild;
import java.time.Duration;
import java.util.*;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.common.TopicPartition;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class AdminKafkaOffsetSnapshotter implements KafkaOffsetSnapshotter,AutoCloseable {
    private final Admin admin; private final JdbcClient jdbc;
    public AdminKafkaOffsetSnapshotter(JdbcClient jdbc,@Value("${verification.kafka-bootstrap-servers:localhost:29092}") String servers){this(jdbc,Admin.create(Map.of(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG,servers)));}
    AdminKafkaOffsetSnapshotter(JdbcClient jdbc,Admin admin){this.jdbc=jdbc;this.admin=admin;}
    public Map<TopicPartition,Long> endOffsets(String topic){return offsets(topic,OffsetSpec.latest());}
    public void assertRetained(String topic,Map<TopicPartition,Long> required){
        Map<TopicPartition,Long> beginnings=offsets(topic,OffsetSpec.earliest()), ends=endOffsets(topic);
        validateRequired(beginnings,ends,required);
    }
    static void validateRequired(Map<TopicPartition,Long> beginnings,Map<TopicPartition,Long> ends,Map<TopicPartition,Long> required){if(required==null||required.size()!=3||ends.size()!=3||beginnings.size()!=3||!required.keySet().equals(ends.keySet())||!beginnings.keySet().equals(ends.keySet()))throw new IllegalArgumentException("exactly configured three partitions required");required.forEach((partition,offset)->{if(offset==null||offset<0||offset>ends.get(partition))throw new IllegalArgumentException("invalid required offset");if(offset<beginnings.get(partition))throw new RequiredOffsetExpiredException(partition,offset,beginnings.get(partition));});}
    @Transactional public Map<TopicPartition,Long> captureAndPersist(UUID runId,String topic){Map<TopicPartition,Long> captured=endOffsets(topic);if(captured.size()!=3)throw new IllegalStateException("expected exactly three partitions");captured.forEach((partition,offset)->jdbc.sql("INSERT INTO rebuild_partition_offset(run_id,phase,topic_name,partition_id,next_offset) VALUES(UUID_TO_BIN(:run),'START',:topic,:partition,:offset)").param("run",runId.toString()).param("topic",topic).param("partition",partition.partition()).param("offset",offset).update());return captured;}
    private Map<TopicPartition,Long> offsets(String topic,OffsetSpec spec){try{var description=admin.describeTopics(List.of(topic)).allTopicNames().get().get(topic);Map<TopicPartition,OffsetSpec> request=new LinkedHashMap<>();description.partitions().forEach(info->request.put(new TopicPartition(topic,info.partition()),spec));var result=admin.listOffsets(request).all().get();Map<TopicPartition,Long> values=new LinkedHashMap<>();result.forEach((partition,info)->values.put(partition,info.offset()));return Map.copyOf(values);}catch(Exception e){throw new IllegalStateException("cannot read Kafka offsets",e);}}
    public void close(){admin.close(Duration.ofSeconds(5));}
}
