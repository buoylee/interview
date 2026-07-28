package com.interview.mysqlescdc.verifier.rebuild;
import org.apache.kafka.common.TopicPartition;
public final class RequiredOffsetExpiredException extends IllegalStateException {
    public RequiredOffsetExpiredException(TopicPartition partition,long required,long beginning){super("required offset "+required+" for "+partition+" is before beginning "+beginning);}
}
