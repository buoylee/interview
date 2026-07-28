package com.interview.mysqlescdc.consumer.rebuild;

import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.listener.MessageListenerContainer;
import org.springframework.stereotype.Component;

@Component
public final class KafkaPrimaryConsumerControl implements PrimaryConsumerControl {
    static final String LISTENER_ID = "product-search-main";
    private final KafkaListenerEndpointRegistry registry;
    public KafkaPrimaryConsumerControl(KafkaListenerEndpointRegistry registry) { this.registry = registry; }
    public PrimaryConsumerStatus pause() { var c = required(); c.pause(); return snapshot(c); }
    public PrimaryConsumerStatus resume() { var c = required(); c.resume(); return snapshot(c); }
    public PrimaryConsumerStatus status() { return snapshot(required()); }
    private MessageListenerContainer required() {
        var c = registry.getListenerContainer(LISTENER_ID);
        if (c == null) throw new IllegalStateException("primary listener missing");
        if (!c.isRunning()) throw new IllegalStateException("primary listener not running");
        return c;
    }
    private static PrimaryConsumerStatus snapshot(MessageListenerContainer c) {
        return new PrimaryConsumerStatus(c.isRunning(), c.isPauseRequested(), null);
    }
}
