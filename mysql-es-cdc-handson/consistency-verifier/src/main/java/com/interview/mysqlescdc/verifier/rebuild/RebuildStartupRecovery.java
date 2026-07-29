package com.interview.mysqlescdc.verifier.rebuild;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

@Component
final class RebuildStartupRecovery {
    private final RebuildRunStore store;
    private final RebuildCoordinator coordinator;

    RebuildStartupRecovery(RebuildRunStore store, RebuildCoordinator coordinator) {
        this.store = store;
        this.coordinator = coordinator;
    }

    @EventListener(ApplicationReadyEvent.class)
    void recover() {
        for (var runId : store.nonterminal()) {
            try { coordinator.resume(runId); }
            catch (RuntimeException deliberatelyFailClosed) {
                // Durable state and gate ownership expose the failed-closed result.
            }
        }
    }
}
