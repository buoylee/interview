package com.interview.mysqlescdc.verifier.diff;

import java.util.Iterator;
import java.util.Objects;
import java.util.UUID;
import java.util.function.Consumer;

import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.target.IndexedDocument;

public record VerificationInput(
        UUID runId,
        long sourceWatermarkStart,
        long sourceWatermarkEnd,
        Iterator<ExpectedDocument> expected,
        Iterator<IndexedDocument> actual,
        Consumer<DocumentDifference> differenceSink) {

    public VerificationInput {
        Objects.requireNonNull(runId, "runId");
        Objects.requireNonNull(expected, "expected");
        Objects.requireNonNull(actual, "actual");
        Objects.requireNonNull(differenceSink, "differenceSink");
        if (sourceWatermarkStart < 0 || sourceWatermarkEnd < 0) {
            throw new IllegalArgumentException("watermarks must be non-negative");
        }
    }
}
