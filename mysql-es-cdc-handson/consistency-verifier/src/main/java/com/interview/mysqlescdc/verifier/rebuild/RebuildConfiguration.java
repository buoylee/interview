package com.interview.mysqlescdc.verifier.rebuild;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
class RebuildConfiguration {
    @Bean RebuildCoordinator rebuildCoordinator(RebuildRunStore store,
            DefaultRebuildWorkflow workflow, RebuildFailpointRegistry failpoints,
            RebuildAdvisoryLock lock) {
        return new RebuildCoordinator(store, workflow, failpoints, lock);
    }
}
