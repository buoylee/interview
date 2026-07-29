package com.interview.mysqlescdc.verifier.rebuild;
import java.time.Duration;import java.util.Map;import org.apache.kafka.common.TopicPartition;
public interface BarrierObserver{Map<TopicPartition,Long> awaitAll(String topic,Barrier barrier,Map<TopicPartition,Long> prePublicationOffsets,Duration timeout);}
