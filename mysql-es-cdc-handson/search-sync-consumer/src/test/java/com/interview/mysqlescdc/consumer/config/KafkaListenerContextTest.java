package com.interview.mysqlescdc.consumer.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.listener.ContainerProperties;
import org.springframework.kafka.listener.DefaultErrorHandler;

@SpringBootTest(properties = "spring.kafka.listener.auto-startup=false")
class KafkaListenerContextTest {
    @Autowired
    private ConcurrentKafkaListenerContainerFactory<?, ?> kafkaListenerContainerFactory;

    @Autowired
    private ConsumerFactory<?, ?> consumerFactory;

    @Autowired
    private DefaultErrorHandler pipelineErrorHandler;

    @Test
    void application_context_wires_the_offset_holding_listener_contract() {
        assertThat(consumerFactory.getConfigurationProperties())
                .containsEntry(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
        assertThat(kafkaListenerContainerFactory.getContainerProperties().getAckMode())
                .isEqualTo(ContainerProperties.AckMode.MANUAL_IMMEDIATE);
        assertThat(kafkaListenerContainerFactory.getContainerProperties().isSyncCommits()).isTrue();
        assertThat(pipelineErrorHandler.isAckAfterHandle()).isFalse();
    }
}
