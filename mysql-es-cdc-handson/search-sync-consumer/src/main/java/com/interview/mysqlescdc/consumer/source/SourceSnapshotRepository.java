package com.interview.mysqlescdc.consumer.source;

import java.util.Optional;

public interface SourceSnapshotRepository {
    Optional<SourceProductSnapshot> load(long productId);
}
