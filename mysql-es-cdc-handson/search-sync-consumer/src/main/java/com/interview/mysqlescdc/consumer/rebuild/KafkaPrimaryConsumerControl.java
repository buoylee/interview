package com.interview.mysqlescdc.consumer.rebuild;

import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.listener.MessageListenerContainer;
import org.springframework.stereotype.Component;

@Component
public final class KafkaPrimaryConsumerControl implements PrimaryConsumerControl {
    static final String LISTENER_ID = "product-search-main";
    private final KafkaListenerEndpointRegistry registry;
    public KafkaPrimaryConsumerControl(KafkaListenerEndpointRegistry registry) { this.registry = registry; }
    public PrimaryConsumerStatus pause() { var c = required(); c.pause(); await(c,true); return snapshot(c); }
    public PrimaryConsumerStatus resume() { var c = required(); c.resume(); await(c,false); return snapshot(c); }
    public PrimaryConsumerStatus status() { return snapshot(required()); }
    private MessageListenerContainer required() {
        var c = registry.getListenerContainer(LISTENER_ID);
        if (c == null) throw new IllegalStateException("primary listener missing");
        if (!c.isRunning()) throw new IllegalStateException("primary listener not running");
        return c;
    }
    private static PrimaryConsumerStatus snapshot(MessageListenerContainer c) {
        return new PrimaryConsumerStatus(c.isRunning(), c.isContainerPaused(), null);
    }
    private static void await(MessageListenerContainer c,boolean paused){long deadline=System.nanoTime()+java.time.Duration.ofSeconds(5).toNanos();while(c.isContainerPaused()!=paused&&System.nanoTime()<deadline){try{Thread.sleep(25);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IllegalStateException("primary control interrupted");}}if(c.isContainerPaused()!=paused)throw new IllegalStateException("primary pause transition timeout");}
}
