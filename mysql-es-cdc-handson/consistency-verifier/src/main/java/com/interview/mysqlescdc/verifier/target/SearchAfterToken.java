package com.interview.mysqlescdc.verifier.target;

import java.util.List;

import tools.jackson.databind.JsonNode;

public record SearchAfterToken(List<JsonNode> sortValues) {
    public SearchAfterToken {
        sortValues = sortValues.stream().map(JsonNode::deepCopy).toList();
        if (sortValues.isEmpty() || sortValues.stream().anyMatch(value -> value == null || value.isNull())) {
            throw new IllegalArgumentException("search_after requires non-null sort values");
        }
    }

    @Override
    public List<JsonNode> sortValues() {
        return sortValues.stream().map(JsonNode::deepCopy).toList();
    }
}
