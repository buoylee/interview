package com.interview.mysqlescdc.consumer.lab;

import java.util.concurrent.atomic.AtomicReference;

import org.springframework.stereotype.Component;

@Component
public final class ProjectionFaultRegistry {
    private final AtomicReference<ProjectionFaultMode> mode =
            new AtomicReference<>(ProjectionFaultMode.NONE);

    public ProjectionFaultMode current() {
        return mode.get();
    }

    public ProjectionFaultMode arm(ProjectionFaultMode requested) {
        mode.set(requested);
        return current();
    }

    public ProjectionFaultMode clear() {
        return arm(ProjectionFaultMode.NONE);
    }
}
