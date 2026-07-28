package com.interview.mysqlescdc.verifier.source;

import java.util.Optional;

public interface ExpectedDocumentReader {
    ExpectedPage readAfter(long exclusiveProductId, int pageSize);

    Optional<ExpectedDocument> load(long productId);
}
