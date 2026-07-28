package com.interview.mysqlescdc.verifier.target;

public interface IndexedDocumentReader {
    TargetCursor open(String indexOrAlias);

    IndexedPage readAfter(TargetCursor cursor, SearchAfterToken token, int pageSize);
}
