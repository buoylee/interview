package com.interview.mysqlescdc.verifier.diff;

import java.util.List;
import java.util.Objects;

import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.target.IndexedDocument;

public record DocumentDifference(
        long productId,
        DifferenceType type,
        ExpectedDocument expected,
        IndexedDocument actual,
        List<FieldDifference> fields) {

    public DocumentDifference {
        if (productId < 1) throw new IllegalArgumentException("positive productId required");
        Objects.requireNonNull(type, "type");
        fields = List.copyOf(fields);
    }

    public static DocumentDifference missing(ExpectedDocument expected) {
        return new DocumentDifference(
                expected.productId(), DifferenceType.MISSING, expected, null, List.of());
    }

    public static DocumentDifference extra(IndexedDocument actual) {
        return new DocumentDifference(
                actual.productId(), DifferenceType.EXTRA, null, actual, List.of());
    }
}
