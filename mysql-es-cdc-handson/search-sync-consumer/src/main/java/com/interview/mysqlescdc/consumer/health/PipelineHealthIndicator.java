package com.interview.mysqlescdc.consumer.health;

import org.springframework.boot.health.contributor.*;
import org.springframework.stereotype.Component;

@Component("pipeline")
public class PipelineHealthIndicator implements HealthIndicator {
    private final PipelineStateRegistry registry;
    public PipelineHealthIndicator(PipelineStateRegistry registry){this.registry=registry;}
    @Override public Health health(){
        PipelineState state=registry.current();
        return switch(state){
            case HEALTHY -> Health.up().withDetail("pipelineState",state).build();
            case CATCHING_UP -> Health.status(Status.UNKNOWN).withDetail("pipelineState",state).build();
            case DEGRADED -> Health.down().withDetail("pipelineState",state).build();
            default -> throw new IllegalStateException("M2-M3 cannot activate rebuild state: "+state);
        };
    }
}
