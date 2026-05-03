package com.interview.financialconsistency.serviceprototype.outbox;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/outbox")
public class OutboxPublishController {
    private static final int MIN_BATCH_SIZE = 1;
    private static final int MAX_BATCH_SIZE = 100;

    private final OutboxPublisher outboxPublisher;

    public OutboxPublishController(OutboxPublisher outboxPublisher) {
        this.outboxPublisher = outboxPublisher;
    }

    @PostMapping("/publish-once")
    public PublishOnceResponse publishOnce(@RequestParam(defaultValue = "10") int batchSize) {
        if (batchSize < MIN_BATCH_SIZE || batchSize > MAX_BATCH_SIZE) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "batchSize must be between " + MIN_BATCH_SIZE + " and " + MAX_BATCH_SIZE);
        }
        return new PublishOnceResponse(outboxPublisher.publishBatch(batchSize));
    }

    public record PublishOnceResponse(int published) {
    }
}
