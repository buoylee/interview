package com.interview.mysqlescdc.consumer.failpoint;

import java.util.EnumMap;
import java.util.Map;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicInteger;

import org.springframework.stereotype.Component;

@Component
public final class FailpointRegistry {
    private final Map<Failpoint, AtomicInteger> counters = new EnumMap<>(Failpoint.class);
    private final CrashAction crashAction;

    public FailpointRegistry(CrashAction crashAction) {
        this.crashAction = crashAction;
        for (Failpoint failpoint : Failpoint.values()) {
            counters.put(failpoint, new AtomicInteger());
        }
    }

    public void arm(Failpoint failpoint, int hits) {
        if (hits < 1 || hits > 100) {
            throw new IllegalArgumentException("hits must be in 1..100");
        }
        counters.get(failpoint).set(hits);
    }

    public void clear() {
        counters.values().forEach(counter -> counter.set(0));
    }

    public Map<Failpoint, Integer> remaining() {
        Map<Failpoint, Integer> snapshot = new EnumMap<>(Failpoint.class);
        counters.forEach((failpoint, counter) -> snapshot.put(failpoint, counter.get()));
        return Collections.unmodifiableMap(snapshot);
    }

    public void hit(Failpoint failpoint) {
        int previous = counters.get(failpoint)
                .getAndUpdate(value -> value > 0 ? value - 1 : 0);
        if (previous > 0) {
            crashAction.crash(86);
        }
    }
}
