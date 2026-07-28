package com.interview.mysqlescdc.verifier.rebuild;

import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

@Component
public final class HttpShadowReplayClient implements ShadowReplayClient {
    private static final Duration TIMEOUT=Duration.ofSeconds(5); private final HttpClient http; private final JsonMapper json; private final String base;
    @Autowired public HttpShadowReplayClient(@Value("${verification.consumer-url:http://localhost:8082}") String base){this(HttpClient.newBuilder().connectTimeout(TIMEOUT).build(),JsonMapper.builder().build(),base);}
    HttpShadowReplayClient(HttpClient http,JsonMapper json,String base){this.http=http;this.json=json;this.base=base.replaceAll("/+$","");}
    public ControlStatus start(UUID runId,String topic,String target,Map<Integer,Long> offsets){return send("/internal/rebuild/shadow","POST",Map.of("runId",runId,"topic",topic,"target",target,"offsets",offsets));}
    public ControlStatus status(UUID runId){return send("/internal/rebuild/shadow/"+runId,"GET",null);}
    public ControlStatus stop(UUID runId){return send("/internal/rebuild/shadow/"+runId,"DELETE",null);}
    public ControlStatus pausePrimary(){return send("/internal/rebuild/primary/pause","POST",Map.of());}
    public ControlStatus resumePrimary(){return send("/internal/rebuild/primary/resume","POST",Map.of());}
    private ControlStatus send(String path,String method,Object body){try{var b=HttpRequest.newBuilder(URI.create(base+path)).timeout(TIMEOUT);if("GET".equals(method))b.GET();else if("DELETE".equals(method))b.DELETE();else b.header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body)));var response=http.send(b.build(),HttpResponse.BodyHandlers.ofString());if(response.statusCode()/100!=2)throw new IllegalStateException("consumer control HTTP "+response.statusCode());return json.readValue(response.body(),ControlStatus.class);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IllegalStateException("consumer control interrupted");}catch(Exception e){throw new IllegalStateException("consumer control failed",e);}}
}
