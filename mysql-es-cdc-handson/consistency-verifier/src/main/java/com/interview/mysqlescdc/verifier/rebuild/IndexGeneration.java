package com.interview.mysqlescdc.verifier.rebuild;
import java.time.Instant;
import java.util.UUID;
public record IndexGeneration(UUID runId,String name,Instant createdAt) {}
