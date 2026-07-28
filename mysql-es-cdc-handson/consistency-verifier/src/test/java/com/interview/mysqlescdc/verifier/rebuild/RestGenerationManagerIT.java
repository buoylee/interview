package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import tools.jackson.databind.json.JsonMapper;

class RestGenerationManagerIT {
    static final String ES="http://127.0.0.1:9200";
    final HttpClient http=HttpClient.newHttpClient();
    final JsonMapper json=JsonMapper.builder().build();
    final Instant now=Instant.parse("2026-07-22T12:00:00Z");
    JdbcClient root; RestGenerationManager manager;
    @BeforeEach void setup() {
        root=JdbcClient.create(new DriverManagerDataSource("jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true","root","rootpass"));
        root.sql("DELETE FROM rebuild_partition_offset").update(); root.sql("DELETE FROM canal_position_recovery").update(); root.sql("DELETE FROM rebuild_run").update();
        deleteTestIndices();
        detachServingAliases();
        createOld("m5_old");
        manager=new RestGenerationManager(JdbcClient.create(new DriverManagerDataSource("jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true","verifier","verifierpass")),http,json,ES,Clock.fixed(now,ZoneOffset.UTC));
    }
    @AfterEach void cleanup(){ detachServingAliases();deleteTestIndices();createAliases("products_v2"); }
    @Test void reserves_before_create_and_applies_exact_template_meta() throws Exception {
        UUID run=UUID.fromString("aaaaaaaa-0000-0000-0000-000000000001");
        IndexGeneration generation=manager.create(run);
        assertThat(generation.name()).isEqualTo("products_v3_20260722120000_aaaaaaaa");
        var mapping=json.readTree(request("GET","/"+generation.name()+"/_mapping",null,200));
        var mappings=mapping.path(generation.name()).path("mappings");
        assertThat(mappings.path("dynamic").asText()).isEqualTo("strict");
        assertThat(mappings.path("properties").size()).isEqualTo(11);
        assertThat(mappings.path("_meta").path("schema_version").asInt()).isEqualTo(3);
        assertThat(mappings.path("_meta").path("deletion_mode").asText()).isEqualTo("tombstone");
        assertThat(mappings.path("_meta").path("rebuild_run_id").asText()).isEqualTo(run.toString());
        assertThat(root.sql("SELECT generation_name FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)").param("run",run.toString()).query(String.class).single()).isEqualTo(generation.name());
        assertThatThrownBy(() -> manager.create(run)).isInstanceOf(RuntimeException.class);
    }
    @Test void deterministic_name_conflict_and_preexisting_index_fail_closed_without_reuse() {
        UUID first=UUID.fromString("bbbbbbbb-0000-0000-0000-000000000001"); manager.create(first);
        UUID samePrefix=UUID.fromString("bbbbbbbb-1111-1111-1111-111111111111");
        assertThatThrownBy(() -> manager.create(samePrefix)).isInstanceOf(RuntimeException.class);
        UUID pre=UUID.fromString("cccccccc-0000-0000-0000-000000000001");
        request("PUT","/products_v3_20260722120000_cccccccc","{}",200);
        assertThatThrownBy(() -> manager.create(pre)).isInstanceOf(RuntimeException.class);
        assertThat(root.sql("SELECT COUNT(*) FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)").param("run",pre.toString()).query(Long.class).single()).isOne();
    }
    @Test void cutover_is_atomic_exact_and_durably_idempotent() {
        IndexGeneration generation=manager.create(UUID.randomUUID());
        AliasCutoverResult result=manager.atomicCutover(generation);
        assertThat(result.oldIndex()).isEqualTo("m5_old"); assertThat(result.alreadyApplied()).isFalse();
        assertExactAliases(generation.name());
        assertThat(root.sql("SELECT alias_swapped FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)").param("run",generation.runId().toString()).query(Boolean.class).single()).isTrue();
        assertThat(manager.atomicCutover(generation).alreadyApplied()).isTrue();
    }
    @Test void whole_alias_request_failure_leaves_old_topology_unchanged() {
        UUID run=UUID.randomUUID(); String missing="products_v3_20260722120000_"+run.toString().substring(0,8);
        root.sql("INSERT INTO rebuild_run(run_id,generation_name,status) VALUES(UUID_TO_BIN(:run),:name,'CREATED')").param("run",run.toString()).param("name",missing).update();
        assertThatThrownBy(() -> manager.atomicCutover(new IndexGeneration(run,missing,now))).isInstanceOf(RuntimeException.class);
        assertExactAliases("m5_old");
    }
    @Test void corrupt_alias_topologies_are_never_normalized() {
        IndexGeneration generation=manager.create(UUID.randomUUID());
        request("POST","/_aliases","{\"actions\":[{\"remove\":{\"index\":\"m5_old\",\"alias\":\"products_search\"}}]}",200);
        assertThatThrownBy(() -> manager.atomicCutover(generation)).isInstanceOf(RuntimeException.class);
        detachServingAliases(); createAliases("m5_old");
        request("POST","/_aliases","{\"actions\":[{\"add\":{\"index\":\"m5_old\",\"alias\":\"products_search\",\"filter\":{\"match_all\":{}}}}]}",200);
        assertThatThrownBy(() -> manager.atomicCutover(generation)).isInstanceOf(RuntimeException.class);
        detachServingAliases(); createAliases("m5_old"); request("PUT","/m5_old2","{}",200);
        request("POST","/_aliases","{\"actions\":[{\"add\":{\"index\":\"m5_old2\",\"alias\":\"products_search\",\"filter\":{\"term\":{\"searchable\":true}}}}]}",200);
        assertThatThrownBy(() -> manager.atomicCutover(generation)).isInstanceOf(RuntimeException.class);
        detachServingAliases();
        request("POST","/_aliases","{\"actions\":[{\"add\":{\"index\":\"m5_old\",\"alias\":\"products_write\"}},{\"add\":{\"index\":\"m5_old\",\"alias\":\"products_search\",\"filter\":{\"term\":{\"searchable\":true}}}}]}",200);
        assertThatThrownBy(() -> manager.atomicCutover(generation)).isInstanceOf(RuntimeException.class);
        detachServingAliases();
        request("POST","/_aliases","{\"actions\":[{\"add\":{\"index\":\"m5_old\",\"alias\":\"products_write\",\"is_write_index\":true,\"routing\":\"unexpected\"}},{\"add\":{\"index\":\"m5_old\",\"alias\":\"products_search\",\"filter\":{\"term\":{\"searchable\":true}}}}]}",200);
        assertThatThrownBy(() -> manager.atomicCutover(generation)).isInstanceOf(RuntimeException.class);
    }
    void createOld(String index){request("PUT","/"+index,"{}",200);createAliases(index);}
    void createAliases(String index){request("POST","/_aliases","{\"actions\":[{\"add\":{\"index\":\""+index+"\",\"alias\":\"products_write\",\"is_write_index\":true}},{\"add\":{\"index\":\""+index+"\",\"alias\":\"products_search\",\"filter\":{\"term\":{\"searchable\":true}}}}]}",200);}
    void detachServingAliases(){try{var node=json.readTree(request("GET","/_alias/products_search,products_write",null,200,404));if(!node.isObject())return;var body=json.createObjectNode();var actions=body.putArray("actions");for(String index:node.propertyNames()){var aliases=node.path(index).path("aliases");for(String alias:aliases.propertyNames())actions.addObject().putObject("remove").put("index",index).put("alias",alias);}if(!actions.isEmpty())request("POST","/_aliases",json.writeValueAsString(body),200);}catch(Exception ignored){}}
    void deleteTestIndices(){try{var list=json.readTree(request("GET","/_cat/indices/products_v3_*,m5_old*?format=json&h=index",null,200));for(var item:list)request("DELETE","/"+item.path("index").asText(),null,200,404);}catch(RuntimeException ignored){}}
    void assertExactAliases(String index){var node=json.readTree(request("GET","/_alias/products_search,products_write",null,200));assertThat(node.size()).isOne();assertThat(node.path(index).path("aliases").size()).isEqualTo(2);assertThat(node.path(index).path("aliases").path("products_write").path("is_write_index").asBoolean()).isTrue();assertThat(node.path(index).path("aliases").path("products_search").path("filter").toString()).isEqualTo("{\"term\":{\"searchable\":true}}");}
    String request(String method,String path,String body,int... expected){try{var b=HttpRequest.newBuilder(URI.create(ES+path)).header("Content-Type","application/json").method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(body));var r=http.send(b.build(),HttpResponse.BodyHandlers.ofString());for(int code:expected)if(r.statusCode()==code)return r.body();throw new AssertionError(r.statusCode()+" "+r.body());}catch(Exception e){throw new RuntimeException(e);}}
}
