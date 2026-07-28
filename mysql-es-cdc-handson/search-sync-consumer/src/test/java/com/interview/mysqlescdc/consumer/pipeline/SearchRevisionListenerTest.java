package com.interview.mysqlescdc.consumer.pipeline;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;
import org.springframework.kafka.support.Acknowledgment;

import com.interview.mysqlescdc.consumer.failpoint.Failpoint;
import com.interview.mysqlescdc.consumer.failpoint.FailpointRegistry;

class SearchRevisionListenerTest {
    private final SyncRecordProcessor processor = mock(SyncRecordProcessor.class);
    private final FailpointRegistry failpoints = mock(FailpointRegistry.class);
    private final Acknowledgment acknowledgment = mock(Acknowledgment.class);
    private final ConsumerRecord<String, String> record = new ConsumerRecord<>("revisions", 0, 1, "k", "v");
    private final SearchRevisionListener listener = new SearchRevisionListener(processor, failpoints);

    @Test
    void checkpoints_follow_processing_and_immediately_precede_ack() {
        when(processor.process(record)).thenReturn(new ProcessingResult(1, 1, 0, 0, 0, 4));
        listener.onRevision(record, acknowledgment);
        InOrder order = inOrder(processor, failpoints, acknowledgment);
        order.verify(processor).process(record);
        order.verify(failpoints).hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        order.verify(failpoints).hit(Failpoint.BEFORE_KAFKA_OFFSET_COMMIT);
        order.verify(acknowledgment).acknowledge();
    }

    @Test
    void processing_failure_never_acknowledges_or_hits_commit_checkpoint() {
        when(processor.process(record)).thenThrow(new RetryablePipelineException("retry"));
        assertThatThrownBy(() -> listener.onRevision(record, acknowledgment))
                .isInstanceOf(RetryablePipelineException.class);
        verify(acknowledgment, never()).acknowledge();
        verify(failpoints, never()).hit(Failpoint.BEFORE_KAFKA_OFFSET_COMMIT);
    }
}
