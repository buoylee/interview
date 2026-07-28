package com.interview.mysqlescdc.consumer.lab;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;

import org.junit.jupiter.api.Test;

import com.interview.mysqlescdc.consumer.projection.SearchDocument;
import com.interview.mysqlescdc.consumer.projection.SearchDocumentProjector;
import com.interview.mysqlescdc.consumer.source.SourceProductSnapshot;

class ProjectionFaultTest {
    private static final Instant UPDATED_AT = Instant.parse("2026-07-22T01:02:03Z");

    @Test
    void category_fault_changes_only_category_name_in_the_consumer_projection() {
        ProjectionFaultRegistry registry = new ProjectionFaultRegistry();
        SearchDocumentProjector projector = new SearchDocumentProjector(registry);
        SourceProductSnapshot source = activeSourceWithCategory(31L, "Displays");
        registry.arm(ProjectionFaultMode.CATEGORY_NAME_FROM_ID);

        SearchDocument document = projector.project(source);

        assertThat(document).isEqualTo(new SearchDocument(
                1001L, "SKU-1001", "Monitor", "4K display",
                31L, "31", 39999L, 7, true, 7L, UPDATED_AT));
    }

    @Test
    void normal_mode_preserves_the_source_category_name() {
        ProjectionFaultRegistry registry = new ProjectionFaultRegistry();
        SearchDocumentProjector projector = new SearchDocumentProjector(registry);

        SearchDocument document = projector.project(activeSourceWithCategory(31L, "Displays"));

        assertThat(document.categoryName()).isEqualTo("Displays");
        assertThat(document.sourceRevision()).isEqualTo(7L);
    }

    private SourceProductSnapshot activeSourceWithCategory(long categoryId, String categoryName) {
        return SourceProductSnapshot.active(
                1001L, "SKU-1001", "Monitor", "4K display",
                categoryId, categoryName, 39999L, 7, 7L, UPDATED_AT);
    }
}
