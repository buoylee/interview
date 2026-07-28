package com.interview.mysqlescdc.consumer.sink;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "pipeline")
public class PipelineElasticsearchProperties {
    private String elasticsearchBaseUrl = "http://127.0.0.1:9200";
    private Duration elasticsearchConnectTimeout = Duration.ofSeconds(2);
    private Duration elasticsearchRequestTimeout = Duration.ofSeconds(5);

    public String getElasticsearchBaseUrl() {
        return elasticsearchBaseUrl;
    }

    public void setElasticsearchBaseUrl(String elasticsearchBaseUrl) {
        this.elasticsearchBaseUrl = elasticsearchBaseUrl;
    }

    public Duration getElasticsearchConnectTimeout() {
        return elasticsearchConnectTimeout;
    }

    public void setElasticsearchConnectTimeout(Duration elasticsearchConnectTimeout) {
        this.elasticsearchConnectTimeout = elasticsearchConnectTimeout;
    }

    public Duration getElasticsearchRequestTimeout() {
        return elasticsearchRequestTimeout;
    }

    public void setElasticsearchRequestTimeout(Duration elasticsearchRequestTimeout) {
        this.elasticsearchRequestTimeout = elasticsearchRequestTimeout;
    }

    String baseUrl() {
        return elasticsearchBaseUrl;
    }

    Duration connectTimeout() {
        return elasticsearchConnectTimeout;
    }

    Duration requestTimeout() {
        return elasticsearchRequestTimeout;
    }
}
