package com.interview.mysqlescdc.consumer.failpoint;

@FunctionalInterface
public interface CrashAction {
    void crash(int exitCode);
}
