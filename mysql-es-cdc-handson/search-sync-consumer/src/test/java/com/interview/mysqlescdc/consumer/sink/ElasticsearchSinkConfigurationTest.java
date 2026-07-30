package com.interview.mysqlescdc.consumer.sink;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import com.interview.mysqlescdc.consumer.lab.ProjectionFaultRegistry;

class ElasticsearchSinkConfigurationTest {
    @Test
    void wires_gateway_and_consumes_base_url_and_timeout_overrides() {
        new ApplicationContextRunner()
                .withUserConfiguration(ElasticsearchSinkConfiguration.class)
                .withBean(ProjectionFaultRegistry.class)
                .withPropertyValues(
                        "pipeline.elasticsearch-base-url=http://example.test:19200/",
                        "pipeline.elasticsearch-connect-timeout=PT3S",
                        "pipeline.elasticsearch-request-timeout=PT7S")
                .run(context -> {
                    assertThat(context).hasSingleBean(ElasticsearchGateway.class);
                    RestElasticsearchGateway gateway = context.getBean(RestElasticsearchGateway.class);
                    assertThat(gateway.bulkUri().toString())
                            .isEqualTo("http://example.test:19200/_bulk?require_alias=true");
                    assertThat(gateway.requestTimeout()).isEqualTo(Duration.ofSeconds(7));
                    assertThat(context.getBean(PipelineElasticsearchProperties.class).connectTimeout())
                            .isEqualTo(Duration.ofSeconds(3));
                });
    }
}
