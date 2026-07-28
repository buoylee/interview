package com.interview.mysqlescdc.consumer.rebuild;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.listener.MessageListenerContainer;

class KafkaPrimaryConsumerControlTest {
    @Test void waits_for_actual_pause_and_resume_state() {
        var registry=mock(KafkaListenerEndpointRegistry.class);var container=mock(MessageListenerContainer.class);var paused=new AtomicBoolean();
        when(registry.getListenerContainer("product-search-main")).thenReturn(container);when(container.isRunning()).thenReturn(true);when(container.isContainerPaused()).thenAnswer(i->paused.get());doAnswer(i->{paused.set(true);return null;}).when(container).pause();doAnswer(i->{paused.set(false);return null;}).when(container).resume();
        var control=new KafkaPrimaryConsumerControl(registry);assertThat(control.pause().paused()).isTrue();assertThat(control.resume().paused()).isFalse();
    }
    @Test void missing_or_not_running_fails_closed() {
        var registry=mock(KafkaListenerEndpointRegistry.class);var control=new KafkaPrimaryConsumerControl(registry);assertThatThrownBy(control::pause).isInstanceOf(IllegalStateException.class);
        var container=mock(MessageListenerContainer.class);when(registry.getListenerContainer("product-search-main")).thenReturn(container);assertThatThrownBy(control::resume).isInstanceOf(IllegalStateException.class);
    }
}
