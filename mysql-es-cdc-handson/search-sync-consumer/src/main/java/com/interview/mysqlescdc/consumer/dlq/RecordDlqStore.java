package com.interview.mysqlescdc.consumer.dlq;

import java.util.Optional;

public interface RecordDlqStore {
    void publish(RecordDlqRecord record);

    Optional<RecordDlqRecord> findPending(String recordId);

    void resolve(String recordId);

    long unresolvedCount();
}
