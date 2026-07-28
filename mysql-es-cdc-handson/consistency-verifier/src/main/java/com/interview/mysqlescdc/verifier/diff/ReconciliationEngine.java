package com.interview.mysqlescdc.verifier.diff;

import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

import org.springframework.stereotype.Component;

import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.target.IndexedDocument;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

@Component
public final class ReconciliationEngine {
    private static final JsonMapper JSON = JsonMapper.builder().findAndAddModules().build();

    public ConsistencyReport compare(VerificationInput input) {
        EnumMap<DifferenceType, Long> counts = new EnumMap<>(DifferenceType.class);
        long expectedCount = 0;
        long actualCount = 0;
        ExpectedDocument expected = next(input.expected());
        IndexedDocument actual = next(input.actual());

        while (expected != null || actual != null) {
            DocumentDifference difference;
            if (actual == null || expected != null && expected.productId() < actual.productId()) {
                difference = DocumentDifference.missing(expected);
                expectedCount++;
                expected = next(input.expected());
            } else if (expected == null || actual.productId() < expected.productId()) {
                difference = DocumentDifference.extra(actual);
                actualCount++;
                actual = next(input.actual());
            } else {
                expectedCount++;
                actualCount++;
                Optional<DocumentDifference> sameId = compareSameId(expected, actual);
                expected = next(input.expected());
                actual = next(input.actual());
                if (sameId.isEmpty()) continue;
                difference = sameId.orElseThrow();
            }
            input.differenceSink().accept(difference);
            counts.merge(difference.type(), 1L, Long::sum);
        }

        long differenceCount = counts.values().stream().mapToLong(Long::longValue).sum();
        return new ConsistencyReport(
                input.runId(), input.sourceWatermarkStart(), input.sourceWatermarkEnd(),
                expectedCount, actualCount, differenceCount, counts,
                input.sourceWatermarkStart() == input.sourceWatermarkEnd());
    }

    private Optional<DocumentDifference> compareSameId(
            ExpectedDocument expected, IndexedDocument actual) {
        if (actual.sourceRevision() > expected.sourceRevision()) {
            return difference(DifferenceType.FUTURE_REVISION, expected, actual, List.of());
        }
        if (actual.sourceRevision() < expected.sourceRevision()) {
            return difference(DifferenceType.STALE, expected, actual, List.of());
        }
        if (actual.searchable() != expected.searchable()) {
            return difference(DifferenceType.TOMBSTONE_MISMATCH, expected, actual,
                    managedFieldDifferences(expected, actual));
        }
        List<FieldDifference> fields = managedFieldDifferences(expected, actual);
        if (!fields.isEmpty()) {
            return difference(DifferenceType.MODIFIED, expected, actual, fields);
        }
        if (actual.elasticsearchVersion() != expected.sourceRevision()) {
            return difference(DifferenceType.VERSION_METADATA_MISMATCH, expected, actual, List.of());
        }
        return Optional.empty();
    }

    private Optional<DocumentDifference> difference(
            DifferenceType type,
            ExpectedDocument expected,
            IndexedDocument actual,
            List<FieldDifference> fields) {
        return Optional.of(new DocumentDifference(
                expected.productId(), type, expected, actual, fields));
    }

    private List<FieldDifference> managedFieldDifferences(
            ExpectedDocument expected, IndexedDocument actual) {
        List<FieldDifference> fields = new ArrayList<>();
        compare(fields, "sku", expected.sku(), actual.sku());
        compare(fields, "name", expected.name(), actual.name());
        compare(fields, "description", expected.description(), actual.description());
        compare(fields, "category_id", expected.categoryId(), actual.categoryId());
        compare(fields, "category_name", expected.categoryName(), actual.categoryName());
        compare(fields, "price_cents", expected.priceCents(), actual.priceCents());
        compare(fields, "available_quantity", expected.availableQuantity(), actual.availableQuantity());
        compare(fields, "searchable", expected.searchable(), actual.searchable());
        compare(fields, "source_updated_at", expected.sourceUpdatedAt(), actual.sourceUpdatedAt());
        return fields;
    }

    private void compare(List<FieldDifference> fields, String field, Object expected, Object actual) {
        if (!Objects.equals(expected, actual)) {
            fields.add(new FieldDifference(field, scalar(expected), scalar(actual)));
        }
    }

    private JsonNode scalar(Object value) {
        if (value instanceof Instant instant) {
            return JSON.valueToTree(instant.toString());
        }
        return JSON.valueToTree(value);
    }

    private static <T> T next(java.util.Iterator<T> iterator) {
        return iterator.hasNext() ? iterator.next() : null;
    }
}
