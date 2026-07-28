package com.interview.mysqlescdc.consumer.pipeline;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

import com.interview.mysqlescdc.consumer.failpoint.Failpoint;
import com.interview.mysqlescdc.consumer.failpoint.FailpointRegistry;

@Component
public class SearchRevisionListener {
    private final SyncRecordProcessor processor;
    private final FailpointRegistry failpoints;

    public SearchRevisionListener(SyncRecordProcessor processor, FailpointRegistry failpoints) {
        this.processor = processor;
        this.failpoints = failpoints;
    }

    @KafkaListener(
            id = "product-search-main",
            topics = "${pipeline.source-topic:product-search-revisions}",
            groupId = "${spring.kafka.consumer.group-id:product-search-sync-v1}",
            ackMode = "MANUAL_IMMEDIATE")
    public void onRevision(
            ConsumerRecord<String, String> record, Acknowledgment acknowledgment) {
        ProcessingResult result = processor.process(record);
        if (result.appliedCount() > 0) {
            failpoints.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        }
        failpoints.hit(Failpoint.BEFORE_KAFKA_OFFSET_COMMIT);
        acknowledgment.acknowledge();
    }
}
