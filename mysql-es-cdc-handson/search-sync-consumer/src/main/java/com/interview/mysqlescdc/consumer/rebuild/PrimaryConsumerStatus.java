package com.interview.mysqlescdc.consumer.rebuild;

public record PrimaryConsumerStatus(boolean running, boolean paused, String failureClass) {}
