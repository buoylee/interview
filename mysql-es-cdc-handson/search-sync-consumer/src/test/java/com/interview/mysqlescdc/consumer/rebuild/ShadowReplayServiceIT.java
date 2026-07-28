package com.interview.mysqlescdc.consumer.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import java.net.URI;
import java.net.http.*;
import java.time.*;
import java.util.*;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import com.interview.mysqlescdc.consumer.canal.CanalRevisionParser;
import com.interview.mysqlescdc.consumer.projection.SearchDocumentProjector;
import com.interview.mysqlescdc.consumer.sink.RestElasticsearchGateway;
import com.interview.mysqlescdc.consumer.source.JdbcSourceSnapshotRepository;
import tools.jackson.databind.json.JsonMapper;

/** Real Kafka/MySQL/Elasticsearch proof; run explicitly after `make up`. */
class ShadowReplayServiceIT {
    static final String TOPIC="product-search-revisions", BOOTSTRAP="127.0.0.1:29092";
    JdbcClient root, product; HttpClient http=HttpClient.newHttpClient(); String target;
    @BeforeEach void setup() throws Exception {
        root=JdbcClient.create(new DriverManagerDataSource("jdbc:mysql://127.0.0.1:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true","root","rootpass"));
        root.sql("GRANT SELECT,INSERT,UPDATE ON product_catalog.rebuild_partition_offset TO 'product'@'%'").update();
        product=JdbcClient.create(new DriverManagerDataSource("jdbc:mysql://127.0.0.1:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true","product","productpass"));
        target="products_v3_"+java.time.format.DateTimeFormatter.ofPattern("yyyyMMddHHmmss").withZone(ZoneOffset.UTC).format(Instant.now())+"_"+UUID.randomUUID().toString().substring(0,8);
        request("PUT","/"+target,"{}");
    }
    @AfterEach void cleanup() throws Exception { request("DELETE","/"+target,null); root.sql("DELETE FROM rebuild_partition_offset WHERE topic_name=:topic").param("topic",TOPIC).update(); root.sql("DELETE FROM rebuild_run WHERE generation_name=:name").param("name",target).update(); }
    @Test void exact_seek_barrier_stale_stop_and_primary_offsets_are_independent() throws Exception {
        long productId=992281L, categoryId=992280L;
        root.sql("INSERT INTO categories(id,name) VALUES(:id,'Replay') ON DUPLICATE KEY UPDATE name='Replay'").param("id",categoryId).update();
        root.sql("INSERT INTO products(id,sku,name,description,category_id,price_cents,status) VALUES(:id,:sku,'Current','v2',:category,100,'ACTIVE') ON DUPLICATE KEY UPDATE name='Current',description='v2',status='ACTIVE'").param("id",productId).param("sku","REPLAY-"+productId).param("category",categoryId).update();
        root.sql("INSERT INTO inventory(product_id,available_quantity,reserved_quantity) VALUES(:id,3,0) ON DUPLICATE KEY UPDATE available_quantity=3,reserved_quantity=0").param("id",productId).update();
        root.sql("INSERT INTO product_search_revision(product_id,revision,active) VALUES(:id,2,TRUE) ON DUPLICATE KEY UPDATE revision=2,active=TRUE").param("id",productId).update();
        Thread.sleep(1500); Map<Integer,Long> start=endOffsets(); UUID run=UUID.randomUUID();
        root.sql("INSERT INTO rebuild_run(run_id,generation_name,status) VALUES(UUID_TO_BIN(:run),:name,'REPLAYING')").param("run",run.toString()).param("name",target).update();
        produce(1,"{\"database\":\"product_catalog\",\"table\":\"cdc_barrier\",\"isDdl\":false,\"id\":8001,\"data\":[{\"partition_token\":\"1\"}]}");
        produce(0,"{\"database\":\"product_catalog\",\"table\":\"product_search_revision\",\"isDdl\":false,\"id\":8002,\"data\":[{\"product_id\":\""+productId+"\",\"revision\":\"1\",\"active\":\"1\"}]}");
        Thread.sleep(1500); Map<TopicPartition,OffsetAndMetadata> primaryBefore=primaryOffsets();
        var json=JsonMapper.builder().build(); var service=new KafkaShadowReplayService(BOOTSTRAP,product,new CanalRevisionParser(json),new JdbcSourceSnapshotRepository(product),new SearchDocumentProjector(),new RestElasticsearchGateway(http,json,"http://127.0.0.1:9200"));
        service.start(new ShadowReplayRequest(run,TOPIC,target,start)); await(service,ShadowReplayState.COMPLETED);
        assertThat(request("GET","/"+target+"/_doc/"+productId,null)).contains("\"source_revision\":2");
        assertThat(primaryOffsets()).isEqualTo(primaryBefore);
        assertThat(service.stop().state()).isEqualTo(ShadowReplayState.COMPLETED);
        assertThat(root.sql("SELECT COUNT(*) FROM rebuild_partition_offset WHERE run_id=UUID_TO_BIN(:run) AND phase='SHADOW'").param("run",run.toString()).query(Long.class).single()).isEqualTo(2);
        Map<Integer,Long> poisonStart=endOffsets(); produce(2,"not-json");
        service.start(new ShadowReplayRequest(run,TOPIC,target,poisonStart)); await(service,ShadowReplayState.FAILED);
        assertThat(service.status().failureClass()).isEqualTo("IllegalArgumentException");
    }
    private void await(KafkaShadowReplayService s,ShadowReplayState expected)throws Exception{Instant end=Instant.now().plusSeconds(15);while(Instant.now().isBefore(end)&&s.status().state()==ShadowReplayState.RUNNING)Thread.sleep(100);assertThat(s.status().state()).isEqualTo(expected);}
    private void produce(int partition,String value)throws Exception{var p=new Properties();p.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,BOOTSTRAP);p.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,StringSerializer.class);p.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,StringSerializer.class);try(var producer=new KafkaProducer<String,String>(p)){producer.send(new ProducerRecord<>(TOPIC,partition,null,value)).get();}}
    private Map<Integer,Long> endOffsets(){var p=new Properties();p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,BOOTSTRAP);p.put(ConsumerConfig.GROUP_ID_CONFIG,"probe-"+UUID.randomUUID());p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,"org.apache.kafka.common.serialization.StringDeserializer");p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,"org.apache.kafka.common.serialization.StringDeserializer");try(var c=new KafkaConsumer<String,String>(p)){var ps=List.of(new TopicPartition(TOPIC,0),new TopicPartition(TOPIC,1),new TopicPartition(TOPIC,2));var e=c.endOffsets(ps);return Map.of(0,e.get(ps.get(0)),1,e.get(ps.get(1)),2,e.get(ps.get(2)));}}
    private Map<TopicPartition,OffsetAndMetadata> primaryOffsets()throws Exception{try(var a=Admin.create(Map.of(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG,BOOTSTRAP))){return Map.copyOf(a.listConsumerGroupOffsets("product-search-sync-v1").partitionsToOffsetAndMetadata().get());}}
    private String request(String method,String path,String body)throws Exception{var b=HttpRequest.newBuilder(URI.create("http://127.0.0.1:9200"+path));if("GET".equals(method))b.GET();else if("DELETE".equals(method))b.DELETE();else b.header("Content-Type","application/json").method(method,HttpRequest.BodyPublishers.ofString(body));var r=http.send(b.build(),HttpResponse.BodyHandlers.ofString());if(r.statusCode()/100!=2&&!("DELETE".equals(method)&&r.statusCode()==404))throw new AssertionError(r.statusCode()+" "+r.body());return r.body();}
}
