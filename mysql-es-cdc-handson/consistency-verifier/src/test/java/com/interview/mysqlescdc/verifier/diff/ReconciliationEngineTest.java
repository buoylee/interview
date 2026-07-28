package com.interview.mysqlescdc.verifier.diff;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.Test;

import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.target.IndexedDocument;

class ReconciliationEngineTest {
    private final ReconciliationEngine engine = new ReconciliationEngine();

    @Test
    void streaming_merge_emits_every_difference_class_and_exact_counts() {
        List<ExpectedDocument> expected = List.of(
                expected(1, 1, true),
                expected(3, 3, true),
                expected(4, 4, true),
                expected(5, 5, true),
                expected(6, 6, false),
                expected(7, 7, true),
                expected(8, 8, true));
        List<IndexedDocument> actual = List.of(
                indexed(expected(2, 2, true), 2),
                changed(indexed(expected(3, 3, true), 3), "Wrong category", null, null),
                indexed(expected(4, 3, true), 3),
                indexed(expected(5, 6, true), 6),
                indexed(expected(6, 6, true), 6),
                indexed(expected(7, 7, true), 99),
                indexed(expected(8, 8, true), 8));
        List<DocumentDifference> emitted = new ArrayList<>();

        ConsistencyReport report = engine.compare(new VerificationInput(
                UUID.fromString("00000000-0000-0000-0000-000000000003"),
                44, 44, expected.iterator(), actual.iterator(), emitted::add));

        assertThat(emitted).extracting(DocumentDifference::type).containsExactly(
                DifferenceType.MISSING,
                DifferenceType.EXTRA,
                DifferenceType.MODIFIED,
                DifferenceType.STALE,
                DifferenceType.FUTURE_REVISION,
                DifferenceType.TOMBSTONE_MISMATCH,
                DifferenceType.VERSION_METADATA_MISMATCH);
        assertThat(report.expectedCount()).isEqualTo(7);
        assertThat(report.actualCount()).isEqualTo(7);
        assertThat(report.differenceCount()).isEqualTo(7);
        assertThat(report.conclusive()).isTrue();
        assertThat(report.counts()).containsEntry(DifferenceType.MODIFIED, 1L);
    }

    @Test
    void modified_reports_every_unequal_managed_field_as_json_scalars() {
        ExpectedDocument expected = expected(20, 9, true);
        IndexedDocument actual = changed(indexed(expected, 9), "Other", 999L,
                Instant.parse("2026-07-22T04:00:00Z"));
        List<DocumentDifference> emitted = new ArrayList<>();

        engine.compare(input(List.of(expected), List.of(actual), emitted));

        assertThat(emitted).singleElement().satisfies(difference -> {
            assertThat(difference.type()).isEqualTo(DifferenceType.MODIFIED);
            assertThat(difference.fields()).extracting(FieldDifference::field)
                    .containsExactly("category_name", "price_cents", "source_updated_at");
            FieldDifference category = difference.fields().getFirst();
            assertThat(category.expectedValue().textValue()).isEqualTo("Category 10");
            assertThat(category.actualValue().textValue()).isEqualTo("Other");
            assertThat(difference.fields().get(1).expectedValue().longValue()).isEqualTo(1020L);
            assertThat(difference.fields().get(1).actualValue().longValue()).isEqualTo(999L);
        });
    }

    @Test
    void same_id_precedence_is_future_then_stale_then_tombstone_then_modified_then_version() {
        List<ExpectedDocument> expected = List.of(
                expected(30, 10, false),
                expected(31, 10, false),
                expected(32, 10, false),
                expected(33, 10, true));
        List<DocumentDifference> emitted = new ArrayList<>();

        engine.compare(input(expected, List.of(
                changed(indexed(expected(30, 11, true), 99), "future wrong", null, null),
                changed(indexed(expected(31, 9, true), 99), "stale wrong", null, null),
                changed(indexed(expected(32, 10, true), 99), "tombstone wrong", null, null),
                changed(indexed(expected(33, 10, true), 99), "modified wins", null, null)), emitted));

        assertThat(emitted).extracting(DocumentDifference::type).containsExactly(
                DifferenceType.FUTURE_REVISION,
                DifferenceType.STALE,
                DifferenceType.TOMBSTONE_MISMATCH,
                DifferenceType.MODIFIED);
    }

    @Test
    void exact_all_eleven_fields_and_version_produces_no_difference_and_watermark_drift_is_inconclusive() {
        ExpectedDocument expected = expected(40, 12, true);
        List<DocumentDifference> emitted = new ArrayList<>();

        ConsistencyReport report = engine.compare(new VerificationInput(
                UUID.randomUUID(), 50, 51,
                List.of(expected).iterator(), List.of(indexed(expected, 12)).iterator(), emitted::add));

        assertThat(emitted).isEmpty();
        assertThat(report.differenceCount()).isZero();
        assertThat(report.conclusive()).isFalse();
    }

    private VerificationInput input(
            List<ExpectedDocument> expected,
            List<IndexedDocument> actual,
            List<DocumentDifference> emitted) {
        return new VerificationInput(
                UUID.randomUUID(), 5, 5, expected.iterator(), actual.iterator(), emitted::add);
    }

    private ExpectedDocument expected(long id, long revision, boolean searchable) {
        Instant updatedAt = Instant.parse("2026-07-22T03:04:05.123456Z");
        if (!searchable) {
            return ExpectedDocument.tombstone(id, revision, updatedAt);
        }
        return new ExpectedDocument(
                id, "SKU-" + id, "Product " + id, "Description " + id,
                10L, "Category 10", 1000L + id, 4, true, revision, updatedAt);
    }

    private IndexedDocument indexed(ExpectedDocument expected, long elasticsearchVersion) {
        return IndexedDocument.fromExpected(expected, elasticsearchVersion, 2, 1);
    }

    private IndexedDocument changed(
            IndexedDocument original,
            String categoryName,
            Long priceCents,
            Instant sourceUpdatedAt) {
        return new IndexedDocument(
                original.productId(), original.sku(), original.name(), original.description(),
                original.categoryId(), categoryName == null ? original.categoryName() : categoryName,
                priceCents == null ? original.priceCents() : priceCents,
                original.availableQuantity(), original.searchable(), original.sourceRevision(),
                sourceUpdatedAt == null ? original.sourceUpdatedAt() : sourceUpdatedAt,
                original.elasticsearchVersion(), original.sequenceNumber(), original.primaryTerm());
    }
}
