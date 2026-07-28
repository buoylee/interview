package com.interview.mysqlescdc.consumer.dlq;

import java.util.Optional;

public interface DlqStore {
    void publish(DlqRecord record);

    Optional<DlqRecord> findPending(String eventId);

    void resolve(String eventId);

    long unresolvedCount();
}
