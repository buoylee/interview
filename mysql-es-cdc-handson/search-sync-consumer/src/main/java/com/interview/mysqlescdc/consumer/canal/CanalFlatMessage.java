package com.interview.mysqlescdc.consumer.canal;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record CanalFlatMessage(
        Long id,
        String database,
        String table,
        Boolean isDdl,
        String type,
        List<Map<String, String>> data) {
}
