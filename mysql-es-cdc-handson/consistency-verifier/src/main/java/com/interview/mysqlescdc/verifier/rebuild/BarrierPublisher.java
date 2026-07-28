package com.interview.mysqlescdc.verifier.rebuild;

import java.util.UUID;

public interface BarrierPublisher { Barrier publish(UUID runId, int partitions); }
