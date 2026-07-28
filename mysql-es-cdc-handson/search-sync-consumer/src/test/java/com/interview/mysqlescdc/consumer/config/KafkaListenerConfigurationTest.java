package com.interview.mysqlescdc.consumer.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import org.junit.jupiter.api.Test;
import org.springframework.boot.kafka.autoconfigure.ConcurrentKafkaListenerContainerFactoryConfigurer;
import org.springframework.boot.kafka.autoconfigure.KafkaProperties;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.listener.ContainerProperties;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.listener.AbstractMessageListenerContainer;
import org.springframework.test.util.ReflectionTestUtils;

class KafkaListenerConfigurationTest {
    private final KafkaListenerConfiguration configuration = new KafkaListenerConfiguration();

    @Test
    void factory_is_manual_immediate_synchronous_and_uses_non_committing_handler() {
        DefaultErrorHandler handler = configuration.pipelineErrorHandler();
        @SuppressWarnings("unchecked")
        ConsumerFactory<Object, Object> consumerFactory = mock(ConsumerFactory.class);
        ConcurrentKafkaListenerContainerFactoryConfigurer configurer =
                new ConcurrentKafkaListenerContainerFactoryConfigurer();
        ReflectionTestUtils.invokeMethod(configurer, "setKafkaProperties", new KafkaProperties());
        ConcurrentKafkaListenerContainerFactory<Object, Object> factory =
                configuration.kafkaListenerContainerFactory(configurer, consumerFactory, handler);

        assertThat(factory.getContainerProperties().getAckMode())
                .isEqualTo(ContainerProperties.AckMode.MANUAL_IMMEDIATE);
        assertThat(factory.getContainerProperties().isSyncCommits()).isTrue();
        AbstractMessageListenerContainer<?, ?> container = factory.createContainer("contract-topic");
        assertThat(container.getCommonErrorHandler()).isSameAs(handler);
        assertThat(handler.isAckAfterHandle()).isFalse();
        assertThat(ReflectionTestUtils.getField(handler, "commitRecovered")).isEqualTo(false);
    }
}
