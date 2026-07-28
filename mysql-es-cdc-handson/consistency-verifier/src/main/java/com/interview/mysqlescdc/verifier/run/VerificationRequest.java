package com.interview.mysqlescdc.verifier.run;

public record VerificationRequest(String target, int pageSize) {
    public VerificationRequest {
        if (target == null || target.isBlank()) throw new IllegalArgumentException("target required");
        if (pageSize < 1 || pageSize > 1_000) {
            throw new IllegalArgumentException("pageSize must be between 1 and 1000");
        }
    }
}
