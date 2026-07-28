package com.interview.mysqlescdc.consumer.sink;

import java.io.IOException;
import java.net.http.HttpRequest;

@FunctionalInterface
interface BulkHttpSender {
    BulkHttpResponse send(HttpRequest request) throws IOException, InterruptedException;
}
