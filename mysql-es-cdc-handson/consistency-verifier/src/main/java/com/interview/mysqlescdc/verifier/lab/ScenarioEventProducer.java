package com.interview.mysqlescdc.verifier.lab;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Properties;
import java.util.Set;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

@Component
@ConditionalOnProperty(name="lab.failpoints.enabled",havingValue="true")
public final class ScenarioEventProducer {
    private static final String TOPIC="product-search-revisions";
    private static final int MAX_PAYLOAD_BYTES=262144;
    private final String bootstrap;private final boolean enabled;private final JsonMapper json=JsonMapper.builder().build();
    public ScenarioEventProducer(@Value("${lab.kafka-bootstrap-servers:localhost:29092}")String bootstrap,
            @Value("${lab.failpoints.enabled:false}")boolean enabled){this.bootstrap=bootstrap;this.enabled=enabled;}
    public Ack send(ScenarioEventRequest request){validate(request);var properties=new Properties();properties.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);properties.put(ProducerConfig.ACKS_CONFIG,"all");properties.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG,"true");properties.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,StringSerializer.class);properties.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,StringSerializer.class);try(var producer=new KafkaProducer<String,String>(properties)){var metadata=producer.send(new ProducerRecord<>(request.topic(),request.partition(),null,request.payload())).get(Duration.ofSeconds(10).toMillis(),java.util.concurrent.TimeUnit.MILLISECONDS);return new Ack(metadata.partition(),metadata.offset());}catch(RuntimeException failure){throw failure;}catch(Exception failure){throw new IllegalStateException("broker ACK failed",failure);}}
    private void validate(ScenarioEventRequest request){if(!enabled)throw new IllegalStateException("lab event injection disabled");if(request==null||!TOPIC.equals(request.topic())||request.partition()<0||request.partition()>2||request.payload()==null||request.payload().getBytes(StandardCharsets.UTF_8).length>MAX_PAYLOAD_BYTES)throw new IllegalArgumentException("exact bounded scenario event required");try{var root=json.readTree(request.payload());var data=root.path("data");if(!root.isObject()||!"product_catalog".equals(root.path("database").asText())||!"product_search_revision".equals(root.path("table").asText())||root.path("isDdl").asBoolean(true)||!Set.of("INSERT","UPDATE","DELETE").contains(root.path("type").asText())||!data.isArray()||data.isEmpty()||data.size()>1000)throw new IllegalArgumentException("flat product_search_revision message required");for(var row:data){var keys=new java.util.HashSet<>(row.propertyNames());if(!row.isObject()||!keys.equals(Set.of("product_id","revision","active"))||!positiveIntegral(row.get("product_id"))||!positiveIntegral(row.get("revision"))||!binary(row.get("active")))throw new IllegalArgumentException("flat revision row required");}}catch(IllegalArgumentException failure){throw failure;}catch(Exception failure){throw new IllegalArgumentException("payload must be valid JSON",failure);}}
    private boolean positiveIntegral(tools.jackson.databind.JsonNode value){if(value==null)return false;if(value.isIntegralNumber())return value.canConvertToLong()&&value.asLong()>0;if(!value.isTextual()||!value.asText().matches("[1-9][0-9]*"))return false;try{return new java.math.BigInteger(value.asText()).compareTo(java.math.BigInteger.valueOf(Long.MAX_VALUE))<=0;}catch(NumberFormatException failure){return false;}}
    private boolean binary(tools.jackson.databind.JsonNode value){return value!=null&&((value.isIntegralNumber()&&(value.asInt()==0||value.asInt()==1))||(value.isTextual()&&Set.of("0","1").contains(value.asText())));}
    public record Ack(int partition,long offset){}
}
