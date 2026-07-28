package com.interview.mysqlescdc.consumer.dlq;

import java.util.Optional;
import java.util.List;

public interface DlqStore {
    void publish(DlqRecord record);

    Optional<DlqRecord> findPending(String eventId);
    List<DlqRecord> listPending();

    void resolve(String eventId);

    long unresolvedCount();
}
