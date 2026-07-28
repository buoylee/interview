package com.interview.mysqlescdc.verifier.rebuild;

import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;

@Component
public final class RestGenerationManager implements GenerationManager {
    private static final DateTimeFormatter STAMP=DateTimeFormatter.ofPattern("yyyyMMddHHmmss").withZone(ZoneOffset.UTC);
    private final JdbcClient jdbc; private final HttpClient http; private final JsonMapper json; private final String base; private final Clock clock;
    public RestGenerationManager(JdbcClient jdbc,@Value("${verification.elasticsearch-url:http://localhost:9200}") String base) {
        this(jdbc,HttpClient.newHttpClient(),JsonMapper.builder().build(),base,Clock.systemUTC());
    }
    RestGenerationManager(JdbcClient jdbc,HttpClient http,JsonMapper json,String base,Clock clock) {
        this.jdbc=jdbc;this.http=http;this.json=json;this.base=base;this.clock=clock;
    }
    @Override public IndexGeneration create(UUID runId) {
        Instant created=clock.instant(); String name="products_v3_"+STAMP.format(created)+"_"+runId.toString().substring(0,8);
        jdbc.sql("INSERT INTO rebuild_run(run_id,generation_name,status) VALUES(UUID_TO_BIN(:run),:name,'CREATED')")
                .param("run",runId.toString()).param("name",name).update();
        try (InputStream input=getClass().getResourceAsStream("/products-v3-template.json")) {
            ObjectNode body=(ObjectNode)json.readTree(input);
            ObjectNode meta=(ObjectNode)body.path("mappings").path("_meta");
            meta.put("rebuild_run_id",runId.toString());meta.put("created_at",created.toString());
            response("PUT","/"+name,json.writeValueAsString(body),200);
            return new IndexGeneration(runId,name,created);
        } catch (RuntimeException exception) { throw exception; }
        catch (Exception exception) { throw new IllegalStateException(exception); }
    }
    @Override public AliasCutoverResult atomicCutover(IndexGeneration generation) {
        AliasState state=aliases();
        if (state.index().equals(generation.name())) {
            if (!swapped(generation.runId())) throw new IllegalStateException("alias moved without durable swapped evidence");
            return new AliasCutoverResult(state.index(),generation.name(),true);
        }
        String old=state.index();
        ObjectNode body=json.createObjectNode(); var actions=body.putArray("actions");
        actions.addObject().putObject("remove").put("index",old).put("alias","products_search");
        actions.addObject().putObject("remove").put("index",old).put("alias","products_write");
        var search=actions.addObject().putObject("add"); search.put("index",generation.name()).put("alias","products_search"); search.putObject("filter").putObject("term").put("searchable",true);
        actions.addObject().putObject("add").put("index",generation.name()).put("alias","products_write").put("is_write_index",true);
        response("POST","/_aliases",json.writeValueAsString(body),200);
        AliasState after=aliases(); if (!after.index().equals(generation.name())) throw new IllegalStateException("cutover topology verification failed");
        jdbc.sql("UPDATE rebuild_run SET alias_swapped=TRUE WHERE run_id=UUID_TO_BIN(:run) AND generation_name=:name")
                .param("run",generation.runId().toString()).param("name",generation.name()).update();
        return new AliasCutoverResult(old,generation.name(),false);
    }
    private AliasState aliases() {
        JsonNode root=json.readTree(response("GET","/_alias/products_search,products_write",null,200));
        if (root.size()!=1) throw new IllegalStateException("aliases must share exactly one index");
        String index=root.propertyNames().iterator().next(); JsonNode aliases=root.path(index).path("aliases");
        JsonNode search=aliases.path("products_search"), write=aliases.path("products_write");
        if (aliases.size()!=2 || search.size()!=1 || !search.path("filter").path("term").path("searchable").asBoolean(false)
                || write.size()!=1 || !write.path("is_write_index").asBoolean(false)) throw new IllegalStateException("corrupt alias topology");
        return new AliasState(index);
    }
    private boolean swapped(UUID run) { return jdbc.sql("SELECT alias_swapped FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)").param("run",run.toString()).query(Boolean.class).single(); }
    private String response(String method,String path,String body,int expected) {
        try { var b=HttpRequest.newBuilder(URI.create(base+path)).timeout(Duration.ofSeconds(10));
            b.method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(body)).header("Content-Type","application/json");
            var r=http.send(b.build(),HttpResponse.BodyHandlers.ofString()); if(r.statusCode()!=expected) throw new IllegalStateException("Elasticsearch "+method+" failed: "+r.statusCode()+" "+r.body()); return r.body();
        } catch(Exception e){ if(e instanceof RuntimeException runtime) throw runtime; throw new IllegalStateException(e); }
    }
    private record AliasState(String index) {}
}
