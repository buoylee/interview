package com.interview.mysqlescdc.consumer.rebuild;
import java.util.*;import org.springframework.jdbc.core.simple.JdbcClient;import org.springframework.stereotype.Component;import org.springframework.transaction.annotation.Transactional;
@Component public class JdbcShadowOffsetStore implements ShadowOffsetStore {
 private final JdbcClient jdbc; public JdbcShadowOffsetStore(JdbcClient jdbc){this.jdbc=jdbc;}
 @Transactional public void initialize(UUID runId,String topic,Map<Integer,Long> offsets){if(!offsets.keySet().equals(Set.of(0,1,2)))throw new IllegalArgumentException("exact offsets required");offsets.forEach((p,o)->jdbc.sql("INSERT INTO rebuild_partition_offset(run_id,phase,topic_name,partition_id,next_offset) VALUES(UUID_TO_BIN(:run),'SHADOW',:topic,:partition,:next)").param("run",runId.toString()).param("topic",topic).param("partition",p).param("next",o).update());}
 public void advance(UUID runId,String topic,int partition,long next){jdbc.sql("UPDATE rebuild_partition_offset SET next_offset=GREATEST(next_offset,:next) WHERE run_id=UUID_TO_BIN(:run) AND phase='SHADOW' AND topic_name=:topic AND partition_id=:partition").param("run",runId.toString()).param("topic",topic).param("partition",partition).param("next",next).update();}
}
