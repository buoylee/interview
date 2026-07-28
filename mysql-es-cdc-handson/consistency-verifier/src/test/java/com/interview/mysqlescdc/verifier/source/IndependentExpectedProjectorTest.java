package com.interview.mysqlescdc.verifier.source;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;

import org.junit.jupiter.api.Test;

class IndependentExpectedProjectorTest {
    private final IndependentExpectedProjector projector = new IndependentExpectedProjector();

    @Test
    void independently_projects_all_active_fields() {
        Instant changedAt = Instant.parse("2026-07-22T03:04:05.123456Z");
        ExpectedSourceRow row = new ExpectedSourceRow(
                3101L, 7L, true, "SKU-3101", "Monitor", "4K",
                31L, "Displays", 39999L, 6, changedAt);

        assertThat(projector.project(row)).isEqualTo(new ExpectedDocument(
                3101L, "SKU-3101", "Monitor", "4K", 31L, "Displays",
                39999L, 6, true, 7L, changedAt));
    }

    @Test
    void independently_projects_inactive_row_as_tombstone() {
        Instant changedAt = Instant.parse("2026-07-22T04:00:00.654321Z");
        ExpectedSourceRow row = ExpectedSourceRow.inactive(3101L, 8L, changedAt);

        assertThat(projector.project(row))
                .isEqualTo(ExpectedDocument.tombstone(3101L, 8L, changedAt));
    }

    @Test
    void source_and_document_records_reject_invalid_active_and_tombstone_states() {
        Instant now = Instant.parse("2026-07-22T04:00:00Z");

        assertThatThrownBy(() -> new ExpectedSourceRow(
                1L, 1L, true, " ", "name", "description",
                1L, "category", 0L, 0, now))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new ExpectedDocument(
                1L, "sku", null, "description", 1L, "category",
                0L, 0, true, 1L, now))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new ExpectedSourceRow(
                1L, 1L, false, "sku", null, null,
                null, null, null, null, now))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> ExpectedDocument.tombstone(0L, 1L, now))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
