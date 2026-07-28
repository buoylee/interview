package com.interview.mysqlescdc.verifier.rebuild;
import java.util.UUID;
public interface GenerationManager {
    IndexGeneration create(UUID runId);
    AliasCutoverResult atomicCutover(IndexGeneration generation);
}
