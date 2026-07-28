package com.interview.mysqlescdc.consumer.rebuild;

public interface PrimaryConsumerControl {
    PrimaryConsumerStatus pause();
    PrimaryConsumerStatus resume();
    PrimaryConsumerStatus status();
}
