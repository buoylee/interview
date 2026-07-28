package com.interview.mysqlescdc.verifier.source;

import org.springframework.stereotype.Component;

@Component
public final class IndependentExpectedProjector {
    public ExpectedDocument project(ExpectedSourceRow row) {
        return row.active() ? projectActiveRevision(row) : projectInactiveRevision(row);
    }

    private ExpectedDocument projectActiveRevision(ExpectedSourceRow row) {
        return new ExpectedDocument(
                row.productId(), row.sku(), row.name(), row.description(),
                row.categoryId(), row.categoryName(), row.priceCents(), row.availableQuantity(),
                true, row.revision(), row.updatedAt());
    }

    private ExpectedDocument projectInactiveRevision(ExpectedSourceRow row) {
        return ExpectedDocument.tombstone(row.productId(), row.revision(), row.updatedAt());
    }
}
