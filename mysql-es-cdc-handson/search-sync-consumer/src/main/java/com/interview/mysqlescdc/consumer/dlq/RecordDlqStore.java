package com.interview.mysqlescdc.consumer.dlq;

import java.util.Optional;
import java.util.List;

public interface RecordDlqStore {
    void publish(RecordDlqRecord record);

    Optional<RecordDlqRecord> findPending(String recordId);
    List<RecordDlqRecord> listPending();

    void resolve(String recordId);

    long unresolvedCount();
}
