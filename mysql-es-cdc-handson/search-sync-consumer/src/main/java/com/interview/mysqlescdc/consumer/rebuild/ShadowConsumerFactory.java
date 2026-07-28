package com.interview.mysqlescdc.consumer.rebuild;
import java.util.UUID;import org.apache.kafka.clients.consumer.Consumer;
public interface ShadowConsumerFactory { Consumer<String,String> create(UUID runId); }
