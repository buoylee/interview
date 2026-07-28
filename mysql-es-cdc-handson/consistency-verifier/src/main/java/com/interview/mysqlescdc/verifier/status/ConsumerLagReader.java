package com.interview.mysqlescdc.verifier.status;

public interface ConsumerLagReader {
    ConsumerLagSnapshot read();
}
