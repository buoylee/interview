package com.interview.mysqlescdc.consumer.rebuild;
public final class RequiredOffsetExpiredException extends RuntimeException { public RequiredOffsetExpiredException(){super("required Kafka offset expired");} }
