package com.interview.mysqlescdc.consumer.failpoint;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public final class ProcessCrashAction implements CrashAction {
    private final boolean enabled;

    public ProcessCrashAction(@Value("${lab.failpoints.enabled:false}") boolean enabled) {
        this.enabled = enabled;
    }

    @Override
    public void crash(int exitCode) {
        if (!enabled) {
            throw new IllegalStateException("process failpoints are disabled");
        }
        Runtime.getRuntime().halt(exitCode);
    }
}
