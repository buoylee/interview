package com.interview.mysqlescdc.consumer.projection;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import com.interview.mysqlescdc.consumer.lab.ProjectionFaultMode;
import com.interview.mysqlescdc.consumer.lab.ProjectionFaultRegistry;
import com.interview.mysqlescdc.consumer.source.SourceProductSnapshot;

@Component
public class SearchDocumentProjector {
    private final ProjectionFaultRegistry faults;

    public SearchDocumentProjector() {
        this(new ProjectionFaultRegistry());
    }

    @Autowired
    public SearchDocumentProjector(ProjectionFaultRegistry faults) {
        this.faults = faults;
    }

    public SearchDocument project(SourceProductSnapshot source) {
        if (!source.active()) {
            return SearchDocument.tombstone(
                    source.productId(), source.revision(), source.updatedAt());
        }
        return new SearchDocument(
                source.productId(),
                source.sku(),
                source.name(),
                source.description(),
                source.categoryId(),
                faults.current() == ProjectionFaultMode.CATEGORY_NAME_FROM_ID
                        ? Long.toString(source.categoryId()) : source.categoryName(),
                source.priceCents(),
                source.availableQuantity(),
                true,
                source.revision(),
                source.updatedAt());
    }
}
