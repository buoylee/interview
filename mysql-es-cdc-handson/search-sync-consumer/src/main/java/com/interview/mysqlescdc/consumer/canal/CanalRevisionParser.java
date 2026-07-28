package com.interview.mysqlescdc.consumer.canal;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.json.JsonMapper;

@Component
public class CanalRevisionParser {
    private final JsonMapper json;

    public CanalRevisionParser(JsonMapper json) {
        this.json = json;
    }

    public List<RevisionSignal> parse(String payload) {
        try {
            CanalFlatMessage message = json.readValue(payload, CanalFlatMessage.class);
            if (Boolean.TRUE.equals(message.isDdl())
                    || !"product_catalog".equals(message.database())
                    || !"product_search_revision".equals(message.table())
                    || message.data() == null) {
                return List.of();
            }

            List<RevisionSignal> signals = new ArrayList<>();
            for (int index = 0; index < message.data().size(); index++) {
                Map<String, String> row = message.data().get(index);
                signals.add(new RevisionSignal(
                        Long.parseLong(required(row, "product_id")),
                        Long.parseLong(required(row, "revision")),
                        parseBoolean(required(row, "active")),
                        message.id(),
                        index));
            }
            return List.copyOf(signals);
        } catch (JacksonException | NumberFormatException exception) {
            throw new IllegalArgumentException("invalid Canal flat message", exception);
        }
    }

    private static String required(Map<String, String> row, String key) {
        if (row == null) {
            throw new IllegalArgumentException("missing Canal data row");
        }
        String value = row.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("missing Canal field: " + key);
        }
        return value;
    }

    private static boolean parseBoolean(String value) {
        if ("1".equals(value) || "true".equalsIgnoreCase(value)) {
            return true;
        }
        if ("0".equals(value) || "false".equalsIgnoreCase(value)) {
            return false;
        }
        throw new IllegalArgumentException("invalid Canal boolean: " + value);
    }
}
