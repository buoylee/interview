package com.interview.mysqlescdc.consumer.sink;

import java.net.http.HttpClient;

import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.json.JsonMapper;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(PipelineElasticsearchProperties.class)
public class ElasticsearchSinkConfiguration {
    @Bean
    @ConditionalOnMissingBean
    JsonMapper elasticsearchJsonMapper() {
        return JsonMapper.builder().findAndAddModules().build();
    }

    @Bean
    RestElasticsearchGateway elasticsearchGateway(
            PipelineElasticsearchProperties properties, JsonMapper json) {
        validate(properties);
        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(properties.connectTimeout())
                .build();
        return new RestElasticsearchGateway(
                client, json, properties.baseUrl(), properties.requestTimeout());
    }

    private static void validate(PipelineElasticsearchProperties properties) {
        if (properties.baseUrl() == null || properties.baseUrl().isBlank()) {
            throw new IllegalArgumentException("pipeline.elasticsearch-base-url must not be blank");
        }
        if (properties.connectTimeout() == null || properties.connectTimeout().isZero()
                || properties.connectTimeout().isNegative()) {
            throw new IllegalArgumentException("pipeline.elasticsearch-connect-timeout must be positive");
        }
        if (properties.requestTimeout() == null || properties.requestTimeout().isZero()
                || properties.requestTimeout().isNegative()) {
            throw new IllegalArgumentException("pipeline.elasticsearch-request-timeout must be positive");
        }
    }
}
