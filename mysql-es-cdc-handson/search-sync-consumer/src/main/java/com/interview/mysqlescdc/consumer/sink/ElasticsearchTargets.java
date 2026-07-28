package com.interview.mysqlescdc.consumer.sink;

import java.util.regex.Pattern;

public final class ElasticsearchTargets {
    private static final Pattern SAFE=Pattern.compile("products_write|products_v3_[0-9]{14}_[0-9a-f]{8}");
    private ElasticsearchTargets() {}
    public static String requireSafe(String target){if(target==null||!SAFE.matcher(target).matches())throw new IllegalArgumentException("unsafe Elasticsearch target");return target;}
}
