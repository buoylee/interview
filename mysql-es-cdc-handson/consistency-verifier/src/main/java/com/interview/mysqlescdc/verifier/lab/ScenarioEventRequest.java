package com.interview.mysqlescdc.verifier.lab;

public record ScenarioEventRequest(String topic, int partition, String payload) {}
