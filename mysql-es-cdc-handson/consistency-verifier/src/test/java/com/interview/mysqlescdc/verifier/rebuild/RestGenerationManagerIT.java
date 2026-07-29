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
import java.nio.file.Files;
import java.nio.file.Path;
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
        Path templatePath=Path.of("../infra/elasticsearch/products-v3-template.json").normalize();
        byte[] templateBefore=Files.readAllBytes(templatePath);
        UUID run=UUID.fromString("aaaaaaaa-0000-0000-0000-000000000001");
        IndexGeneration generation=manager.create(run);
        assertThat(generation.name()).isEqualTo("products_v3_20260722120000_aaaaaaaa");
        var mapping=json.readTree(request("GET","/"+generation.name()+"/_mapping",null,200));
        var mappings=mapping.path(generation.name()).path("mappings");
        assertThat(mappings.path("dynamic").asText()).isEqualTo("strict");
        var template=json.readTree(templateBefore);
        assertThat(mappings.path("properties")).isEqualTo(template.path("mappings").path("properties"));
        assertThat(mappings.path("_meta").path("schema_version").asInt()).isEqualTo(3);
        assertThat(mappings.path("_meta").path("deletion_mode").asText()).isEqualTo("tombstone");
        assertThat(mappings.path("_meta").path("rebuild_run_id").asText()).isEqualTo(run.toString());
        assertThat(mappings.path("_meta").path("created_at").asText()).isEqualTo(now.toString());
        assertThat(mappings.path("_meta").size()).isEqualTo(4);
        var settings=json.readTree(request("GET","/"+generation.name()+"/_settings",null,200)).path(generation.name()).path("settings").path("index");
        assertThat(settings.path("number_of_shards").asText()).isEqualTo("1");
        assertThat(settings.path("number_of_replicas").asText()).isEqualTo("0");
        assertThat(settings.path("refresh_interval").asText()).isEqualTo("1s");
        assertThat(Files.readAllBytes(templatePath)).isEqualTo(templateBefore);
        assertThat(root.sql("SELECT generation_name FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)").param("run",run.toString()).query(String.class).single()).isEqualTo(generation.name());
        assertThatThrownBy(() -> manager.create(run)).isInstanceOf(RuntimeException.class);
    }
    @Test void exact_pre_reserved_created_row_is_verified_then_used_for_es_creation(){UUID run=UUID.fromString("dddddddd-0000-0000-0000-000000000001");String name="products_v3_20260722120000_dddddddd";root.sql("INSERT INTO rebuild_run(run_id,generation_name,status) VALUES(UUID_TO_BIN(:run),:name,'CREATED')").param("run",run.toString()).param("name",name).update();IndexGeneration generation=manager.create(run);assertThat(generation.name()).isEqualTo(name);assertThat(request("GET","/"+name,null,200)).contains(run.toString());}
    @Test void missing_or_conflicting_durable_reservation_rejects_before_alias_side_effect() {
        UUID missing=UUID.randomUUID();
        assertThatThrownBy(() -> manager.atomicCutover(new IndexGeneration(missing,"products_v3_forged",now))).isInstanceOf(RuntimeException.class);
        assertExactAliases("m5_old");
        UUID conflict=UUID.randomUUID();
        root.sql("INSERT INTO rebuild_run(run_id,generation_name,status) VALUES(UUID_TO_BIN(:run),'reserved_other','CREATED')").param("run",conflict.toString()).update();
        assertThatThrownBy(() -> manager.atomicCutover(new IndexGeneration(conflict,"products_v3_forged",now))).isInstanceOf(RuntimeException.class);
        assertExactAliases("m5_old");
    }
    @Test void zero_row_swapped_update_never_returns_success_after_es_side_effect() {
        IndexGeneration generation=manager.create(UUID.randomUUID());
        markCutting(generation);
        var failPersist=new RestGenerationManager(managerJdbc(),http,json,ES,Clock.fixed(now,ZoneOffset.UTC),
                () -> root.sql("DELETE FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)").param("run",generation.runId().toString()).update());
        assertThatThrownBy(() -> failPersist.atomicCutover(generation)).hasMessageContaining("durable swapped evidence");
        assertExactAliases(generation.name());
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
        assertThatThrownBy(() -> manager.atomicCutover(generation)).hasMessageContaining("CUTTING_OVER");
        assertExactAliases("m5_old");
        markCutting(generation);
        AliasCutoverResult result=manager.atomicCutover(generation);
        assertThat(result.oldIndex()).isEqualTo("m5_old"); assertThat(result.alreadyApplied()).isFalse();
        assertExactAliases(generation.name());
        assertThat(root.sql("SELECT alias_swapped FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)").param("run",generation.runId().toString()).query(Boolean.class).single()).isTrue();
        root.sql("UPDATE rebuild_run SET status='CUTOVER_COMMITTED' WHERE run_id=UUID_TO_BIN(:run)").param("run",generation.runId().toString()).update();
        assertThat(manager.atomicCutover(generation).alreadyApplied()).isTrue();
    }
    @Test void whole_alias_request_failure_leaves_old_topology_unchanged() {
        UUID run=UUID.randomUUID(); String missing="products_v3_20260722120000_"+run.toString().substring(0,8);
        root.sql("INSERT INTO rebuild_run(run_id,generation_name,status) VALUES(UUID_TO_BIN(:run),:name,'CUTTING_OVER')").param("run",run.toString()).param("name",missing).update();
        assertThatThrownBy(() -> manager.atomicCutover(new IndexGeneration(run,missing,now))).isInstanceOf(RuntimeException.class);
        assertExactAliases("m5_old");
    }
    @Test void mixed_status_swapped_and_topology_combinations_fail_closed() {
        IndexGeneration generation=manager.create(UUID.randomUUID());
        root.sql("UPDATE rebuild_run SET status='CUTTING_OVER',alias_swapped=TRUE WHERE run_id=UUID_TO_BIN(:run)").param("run",generation.runId().toString()).update();
        assertThatThrownBy(() -> manager.atomicCutover(generation)).isInstanceOf(RuntimeException.class);
        assertExactAliases("m5_old");
        root.sql("UPDATE rebuild_run SET status='COMPLETED',alias_swapped=FALSE WHERE run_id=UUID_TO_BIN(:run)").param("run",generation.runId().toString()).update();
        assertThatThrownBy(() -> manager.atomicCutover(generation)).isInstanceOf(RuntimeException.class);
        assertExactAliases("m5_old");
    }
    @Test void corrupt_alias_topologies_are_never_normalized() {
        IndexGeneration generation=manager.create(UUID.randomUUID());
        markCutting(generation);
        request("POST","/_aliases","{\"actions\":[{\"remove\":{\"index\":\"m5_old\",\"alias\":\"products_search\"}}]}",200);
        assertThatThrownBy(() -> manager.atomicCutover(generation)).isInstanceOf(RuntimeException.class);
        detachServingAliases(); createAliases("m5_old");
        request("POST","/_aliases","{\"actions\":[{\"add\":{\"index\":\"m5_old\",\"alias\":\"products_search\",\"filter\":{\"match_all\":{}}}}]}",200);
        assertThatThrownBy(() -> manager.atomicCutover(generation)).isInstanceOf(RuntimeException.class);
        detachServingAliases();
        request("POST","/_aliases","{\"actions\":[{\"add\":{\"index\":\"m5_old\",\"alias\":\"products_write\",\"is_write_index\":true}},{\"add\":{\"index\":\"m5_old\",\"alias\":\"products_search\",\"filter\":{\"bool\":{\"should\":[{\"term\":{\"searchable\":true}},{\"match_all\":{}}]}}}}]}",200);
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
    JdbcClient managerJdbc(){return JdbcClient.create(new DriverManagerDataSource("jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true","verifier","verifierpass"));}
    void markCutting(IndexGeneration generation){root.sql("UPDATE rebuild_run SET status='CUTTING_OVER' WHERE run_id=UUID_TO_BIN(:run)").param("run",generation.runId().toString()).update();}
    void createAliases(String index){request("POST","/_aliases","{\"actions\":[{\"add\":{\"index\":\""+index+"\",\"alias\":\"products_write\",\"is_write_index\":true}},{\"add\":{\"index\":\""+index+"\",\"alias\":\"products_search\",\"filter\":{\"term\":{\"searchable\":true}}}}]}",200);}
    void detachServingAliases(){try{var node=json.readTree(request("GET","/_alias/products_search,products_write",null,200,404));if(!node.isObject())return;var body=json.createObjectNode();var actions=body.putArray("actions");for(String index:node.propertyNames()){var aliases=node.path(index).path("aliases");for(String alias:aliases.propertyNames())actions.addObject().putObject("remove").put("index",index).put("alias",alias);}if(!actions.isEmpty())request("POST","/_aliases",json.writeValueAsString(body),200);}catch(Exception ignored){}}
    void deleteTestIndices(){try{var list=json.readTree(request("GET","/_cat/indices/products_v3_*,m5_old*?format=json&h=index",null,200));for(var item:list)request("DELETE","/"+item.path("index").asText(),null,200,404);}catch(RuntimeException ignored){}}
    void assertExactAliases(String index){var node=json.readTree(request("GET","/_alias/products_search,products_write",null,200));assertThat(node.size()).isOne();assertThat(node.path(index).path("aliases").size()).isEqualTo(2);assertThat(node.path(index).path("aliases").path("products_write").path("is_write_index").asBoolean()).isTrue();assertThat(node.path(index).path("aliases").path("products_search").path("filter").toString()).isEqualTo("{\"term\":{\"searchable\":true}}");}
    String request(String method,String path,String body,int... expected){try{var b=HttpRequest.newBuilder(URI.create(ES+path)).header("Content-Type","application/json").method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(body));var r=http.send(b.build(),HttpResponse.BodyHandlers.ofString());for(int code:expected)if(r.statusCode()==code)return r.body();throw new AssertionError(r.statusCode()+" "+r.body());}catch(Exception e){throw new RuntimeException(e);}}
}
