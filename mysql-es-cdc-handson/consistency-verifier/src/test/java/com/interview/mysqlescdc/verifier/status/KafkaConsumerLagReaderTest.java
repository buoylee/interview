package com.interview.mysqlescdc.verifier.status;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;

import org.junit.jupiter.api.Test;

class KafkaConsumerLagReaderTest {
    private final KafkaOffsets offsets = mock(KafkaOffsets.class);
    private final PipelineConditionStore conditions = mock(PipelineConditionStore.class);
    private final KafkaConsumerLagReader reader = new KafkaConsumerLagReader(
            offsets, conditions, "events", "projection-v1");

    @Test
    void computes_every_partition_and_missing_commit_is_not_zero_lag() {
        when(offsets.read("events", "projection-v1")).thenReturn(List.of(
                new KafkaOffsetEvidence("events", 0, 7L, 5, 10),
                new KafkaOffsetEvidence("events", 1, null, 2, 8)));

        ConsumerLagSnapshot snapshot = reader.read();

        assertThat(snapshot.totalLag()).isEqualTo(9);
        assertThat(snapshot.allPartitionsCommitted()).isFalse();
        assertThat(snapshot.partitions()).extracting(PartitionLag::lag).containsExactly(3L, 6L);
        verify(conditions, never()).activate(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

    @Test
    void committed_offset_before_beginning_durably_activates_log_gap() {
        when(offsets.read("events", "projection-v1")).thenReturn(List.of(
                new KafkaOffsetEvidence("events", 3, 4L, 9, 12)));

        ConsumerLagSnapshot snapshot = reader.read();

        assertThat(snapshot.totalLag()).isEqualTo(8);
        assertThat(snapshot.partitions().getFirst().retentionGap()).isTrue();
        verify(conditions).activate(org.mockito.ArgumentMatchers.eq("LOG_GAP"),
                argThat(details -> details.length() <= 512
                        && details.contains("\"partition\":3")
                        && details.contains("\"committed\":4")
                        && details.contains("\"beginning\":9")));
    }

    @Test
    void empty_partition_evidence_is_incomplete_not_zero_lag_proof() {
        when(offsets.read("events", "projection-v1")).thenReturn(List.of());

        ConsumerLagSnapshot snapshot = reader.read();

        assertThat(snapshot.totalLag()).isZero();
        assertThat(snapshot.allPartitionsCommitted()).isFalse();
    }
}
