package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.*;
import java.util.*;
import org.apache.kafka.common.TopicPartition;
import org.junit.jupiter.api.Test;

class KafkaOffsetSnapshotterTest {
    private static final String TOPIC="product-search-revisions";
    @Test void retention_validation_rejects_every_fail_closed_boundary() {
        var beginnings=offsets(5,6,7); var ends=offsets(10,11,12);
        assertThatCode(()->AdminKafkaOffsetSnapshotter.validateRequired(beginnings,ends,offsets(5,8,12))).doesNotThrowAnyException();
        assertThatThrownBy(()->AdminKafkaOffsetSnapshotter.validateRequired(beginnings,ends,Map.of())).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(()->AdminKafkaOffsetSnapshotter.validateRequired(beginnings,ends,offsets(-1,8,9))).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(()->AdminKafkaOffsetSnapshotter.validateRequired(beginnings,ends,offsets(5,12,9))).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(()->AdminKafkaOffsetSnapshotter.validateRequired(beginnings,ends,offsets(4,8,9))).isInstanceOf(RequiredOffsetExpiredException.class);
    }
    private static Map<TopicPartition,Long> offsets(long a,long b,long c){return Map.of(new TopicPartition(TOPIC,0),a,new TopicPartition(TOPIC,1),b,new TopicPartition(TOPIC,2),c);}
}
