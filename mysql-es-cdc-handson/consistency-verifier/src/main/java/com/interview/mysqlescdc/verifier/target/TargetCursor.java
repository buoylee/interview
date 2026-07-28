package com.interview.mysqlescdc.verifier.target;

import java.util.Objects;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

public final class TargetCursor implements AutoCloseable {
    @FunctionalInterface
    interface PitCloser {
        void close(String pitId);
    }

    private final AtomicReference<String> pitId;
    private final AtomicBoolean closed = new AtomicBoolean();
    private final PitCloser closer;

    TargetCursor(String pitId, PitCloser closer) {
        this.pitId = new AtomicReference<>(requirePitId(pitId));
        this.closer = Objects.requireNonNull(closer, "closer");
    }

    String pitId() {
        if (closed()) throw new IllegalStateException("target cursor is closed");
        return pitId.get();
    }

    void renew(String renewedPitId) {
        if (renewedPitId != null && !renewedPitId.isBlank()) {
            pitId.set(renewedPitId);
        }
    }

    public boolean closed() {
        return closed.get();
    }

    @Override
    public void close() {
        if (closed.compareAndSet(false, true)) {
            closer.close(pitId.get());
        }
    }

    private static String requirePitId(String value) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException("PIT id required");
        return value;
    }
}
