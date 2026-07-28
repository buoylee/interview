package com.interview.mysqlescdc.consumer.rebuild;
import java.util.Map;import java.util.UUID;
public interface ShadowOffsetStore { void initialize(UUID runId,String topic,Map<Integer,Long> offsets); void advance(UUID runId,String topic,int partition,long nextOffset); }
