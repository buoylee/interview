package com.interview.mysqlescdc.consumer.projection;

import org.springframework.stereotype.Component;

import com.interview.mysqlescdc.consumer.source.SourceProductSnapshot;

@Component
public class SearchDocumentProjector {
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
                source.categoryName(),
                source.priceCents(),
                source.availableQuantity(),
                true,
                source.revision(),
                source.updatedAt());
    }
}
