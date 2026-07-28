package com.interview.mysqlescdc.consumer.sink;

import java.util.List;

import com.interview.mysqlescdc.consumer.projection.SearchDocument;

public interface ElasticsearchGateway {
    BulkWriteResult write(String targetAlias, List<SearchDocument> documents);
}
