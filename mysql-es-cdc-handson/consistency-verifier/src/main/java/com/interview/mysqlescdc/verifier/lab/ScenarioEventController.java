package com.interview.mysqlescdc.verifier.lab;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/internal/lab/scenario-events")
@ConditionalOnProperty(name="lab.failpoints.enabled",havingValue="true")
public final class ScenarioEventController{
 private final ScenarioEventProducer producer;public ScenarioEventController(ScenarioEventProducer producer){this.producer=producer;}
 @PostMapping public ScenarioEventProducer.Ack send(@RequestBody ScenarioEventRequest body,HttpServletRequest request){String remote=request.getRemoteAddr();if(!("127.0.0.1".equals(remote)||"::1".equals(remote)||"0:0:0:0:0:0:0:1".equals(remote)))throw new ResponseStatusException(HttpStatus.FORBIDDEN,"loopback required");return producer.send(body);}
}
