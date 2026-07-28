package com.interview.mysqlescdc.consumer.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import java.net.URI;import java.net.http.*;import java.time.*;import java.util.*;
import org.apache.kafka.clients.admin.*;import org.apache.kafka.clients.producer.*;import org.apache.kafka.common.TopicPartition;import org.apache.kafka.common.serialization.StringSerializer;import org.junit.jupiter.api.Test;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import tools.jackson.databind.json.JsonMapper;

/** Real running-container proof; run explicitly after rebuilding the consumer image. */
class PrimaryConsumerControlIT {
    static final String BOOTSTRAP="127.0.0.1:29092",TOPIC="product-search-revisions",GROUP="product-search-sync-v1";HttpClient http=HttpClient.newHttpClient();JsonMapper json=JsonMapper.builder().build();
    @Test void pause_keeps_committed_offsets_fixed_and_resume_advances()throws Exception{var paused=control("pause");assertThat(paused.path("paused").asBoolean()).isTrue();Map<TopicPartition,OffsetAndMetadata> before=offsets();produce();Thread.sleep(1200);assertThat(offsets()).isEqualTo(before);var resumed=control("resume");assertThat(resumed.path("paused").asBoolean()).isFalse();var partition=new TopicPartition(TOPIC,0);long expected=before.get(partition).offset()+1;Instant deadline=Instant.now().plusSeconds(10);while(Instant.now().isBefore(deadline)&&offsets().get(partition).offset()<expected)Thread.sleep(100);assertThat(offsets().get(partition).offset()).isGreaterThanOrEqualTo(expected);}
    private tools.jackson.databind.JsonNode control(String action)throws Exception{var r=http.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:8082/internal/rebuild/primary/"+action)).POST(HttpRequest.BodyPublishers.noBody()).build(),HttpResponse.BodyHandlers.ofString());assertThat(r.statusCode()).isEqualTo(200);return json.readTree(r.body());}
    private Map<TopicPartition,OffsetAndMetadata> offsets()throws Exception{try(var a=Admin.create(Map.of(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG,BOOTSTRAP))){return Map.copyOf(a.listConsumerGroupOffsets(GROUP).partitionsToOffsetAndMetadata().get());}}
    private void produce()throws Exception{var p=new Properties();p.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,BOOTSTRAP);p.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,StringSerializer.class);p.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,StringSerializer.class);try(var producer=new KafkaProducer<String,String>(p)){producer.send(new ProducerRecord<>(TOPIC,0,null,"{\"database\":\"other\",\"table\":\"ignored\",\"isDdl\":true,\"id\":99001,\"data\":[]}")).get();}}
}
