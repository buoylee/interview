package com.interview.mysqlescdc.verifier.rebuild;
import java.util.UUID;
public record RebuildRequest(UUID runId,String reason,String topic,int pageSize){public RebuildRequest{if(runId==null||reason==null||!"product-search-revisions".equals(topic)||pageSize!=200)throw new IllegalArgumentException("run, supported reason, configured topic and pageSize 200 required");if(!java.util.Set.of("MANUAL","KAFKA_GAP","MYSQL_BINLOG_GAP").contains(reason))throw new IllegalArgumentException("unsupported rebuild reason");}}
