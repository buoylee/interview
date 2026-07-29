package com.interview.mysqlescdc.consumer.lab;

import java.util.concurrent.atomic.AtomicReference;
import java.util.OptionalLong;

import org.springframework.stereotype.Component;

@Component
public final class ProjectionFaultRegistry {
    private final AtomicReference<State> state =
            new AtomicReference<>(new State(ProjectionFaultMode.NONE, null));

    public ProjectionFaultMode current() {
        return state.get().mode();
    }

    public ProjectionFaultMode arm(ProjectionFaultMode requested) {
        state.set(new State(requested, null));
        return current();
    }

    public ProjectionFaultMode arm(ProjectionFaultMode requested, long productId) {
        if (productId <= 0) throw new IllegalArgumentException("positive target product required");
        state.set(new State(requested, productId));
        return current();
    }

    public boolean matches(ProjectionFaultMode expected, long productId) {
        State current = state.get();
        return current.mode() == expected && current.productId() != null
                && current.productId() == productId;
    }

    public OptionalLong targetProductId() {
        Long productId = state.get().productId();
        return productId == null ? OptionalLong.empty() : OptionalLong.of(productId);
    }

    public ProjectionFaultMode clear() {
        return arm(ProjectionFaultMode.NONE);
    }

    private record State(ProjectionFaultMode mode, Long productId) {}
}
