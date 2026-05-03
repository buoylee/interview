package com.interview.financialconsistency.serviceprototype.outbox;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/outbox")
public class OutboxPublishController {
    private final OutboxPublisher outboxPublisher;

    public OutboxPublishController(OutboxPublisher outboxPublisher) {
        this.outboxPublisher = outboxPublisher;
    }

    @PostMapping("/publish-once")
    public PublishOnceResponse publishOnce(@RequestParam(defaultValue = "10") int batchSize) {
        return new PublishOnceResponse(outboxPublisher.publishBatch(batchSize));
    }

    public record PublishOnceResponse(int published) {
    }
}
