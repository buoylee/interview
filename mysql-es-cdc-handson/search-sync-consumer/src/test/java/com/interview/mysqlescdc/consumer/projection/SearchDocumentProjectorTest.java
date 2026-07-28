package com.interview.mysqlescdc.consumer.projection;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

import com.interview.mysqlescdc.consumer.source.SourceProductSnapshot;

class SearchDocumentProjectorTest {
    private final SearchDocumentProjector projector = new SearchDocumentProjector();

    @Test
    void projects_a_complete_active_document() {
        Instant updatedAt = Instant.parse("2026-07-22T01:02:03.123456Z");
        SourceProductSnapshot source = SourceProductSnapshot.active(
                2101L, "SKU-2101", "Keyboard", "Mechanical",
                10L, "Accessories", 12999L, 8, 4L, updatedAt);

        assertThat(projector.project(source)).isEqualTo(new SearchDocument(
                2101L, "SKU-2101", "Keyboard", "Mechanical",
                10L, "Accessories", 12999L, 8, true, 4L, updatedAt));
    }

    @Test
    void projects_an_inactive_source_as_a_versioned_tombstone() {
        Instant updatedAt = Instant.parse("2026-07-22T02:00:00.654321Z");
        SourceProductSnapshot source = SourceProductSnapshot.inactive(2101L, 5L, updatedAt);

        SearchDocument document = projector.project(source);

        assertThat(document).isEqualTo(new SearchDocument(
                2101L, null, null, null, null, null, null, null,
                false, 5L, updatedAt));
    }

    @Test
    void uses_the_locked_json_wire_names() throws Exception {
        SearchDocument document = projector.project(SourceProductSnapshot.active(
                2101L, "SKU-2101", "Keyboard", "Mechanical",
                10L, "Accessories", 12999L, 8, 4L,
                Instant.parse("2026-07-22T01:02:03Z")));

        String json = JsonMapper.builder().findAndAddModules().build().writeValueAsString(document);

        assertThat(json).contains(
                "\"product_id\":2101", "\"category_id\":10",
                "\"category_name\":\"Accessories\"", "\"price_cents\":12999",
                "\"available_quantity\":8", "\"searchable\":true",
                "\"source_revision\":4", "\"source_updated_at\":");
    }

    @Test
    void rejects_partial_blank_or_invalid_active_source_values() {
        Instant timestamp = Instant.parse("2026-07-22T01:02:03Z");

        assertThatThrownBy(() -> new SourceProductSnapshot(
                1L, "SKU", "Name", "", 10L, null, 1L, 0,
                true, 1L, timestamp)).isInstanceOf(RuntimeException.class);
        assertThatThrownBy(() -> SourceProductSnapshot.active(
                1L, " ", "Name", "", 10L, "Category", 1L, 0, 1L, timestamp))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> SourceProductSnapshot.active(
                1L, "SKU", "Name", "", 0L, "Category", 1L, 0, 1L, timestamp))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> SourceProductSnapshot.active(
                1L, "SKU", "Name", "", 10L, "Category", -1L, 0, 1L, timestamp))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> SourceProductSnapshot.active(
                1L, "SKU", "Name", "", 10L, "Category", 1L, -1, 1L, timestamp))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejects_business_fields_on_inactive_source() {
        assertThatThrownBy(() -> new SourceProductSnapshot(
                1L, "SKU", null, null, null, null, null, null,
                false, 1L, Instant.parse("2026-07-22T01:02:03Z")))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejects_partial_blank_or_invalid_searchable_document_values() {
        Instant timestamp = Instant.parse("2026-07-22T01:02:03Z");

        assertThatThrownBy(() -> new SearchDocument(
                1L, "SKU", "Name", "", 10L, null, 1L, 0,
                true, 1L, timestamp)).isInstanceOf(RuntimeException.class);
        assertThatThrownBy(() -> new SearchDocument(
                1L, "SKU", " ", "", 10L, "Category", 1L, 0,
                true, 1L, timestamp)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new SearchDocument(
                1L, "SKU", "Name", "", 0L, "Category", 1L, 0,
                true, 1L, timestamp)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new SearchDocument(
                1L, "SKU", "Name", "", 10L, "Category", -1L, 0,
                true, 1L, timestamp)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new SearchDocument(
                1L, "SKU", "Name", "", 10L, "Category", 1L, -1,
                true, 1L, timestamp)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejects_business_fields_on_non_searchable_document() {
        assertThatThrownBy(() -> new SearchDocument(
                1L, "SKU", null, null, null, null, null, null,
                false, 1L, Instant.parse("2026-07-22T01:02:03Z")))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
