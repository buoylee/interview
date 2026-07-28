package com.interview.mysqlescdc.verifier.rebuild;
import com.interview.mysqlescdc.verifier.source.ExpectedPage;
public interface SourceSnapshotCursor extends AutoCloseable { ExpectedPage readAfter(long exclusiveProductId,int pageSize); @Override void close(); }
