package com.interview.mysqlescdc.consumer.canal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

class CanalRevisionParserTest {
    private final CanalRevisionParser parser =
            new CanalRevisionParser(JsonMapper.builder().build());

    @Test
    void parses_every_revision_row_from_a_flat_message() {
        String payload = """
                {
                  "id": 91,
                  "database": "product_catalog",
                  "table": "product_search_revision",
                  "isDdl": false,
                  "type": "UPDATE",
                  "data": [
                    {"product_id":"1001","revision":"4","active":"1"},
                    {"product_id":"1002","revision":"8","active":"0"}
                  ]
                }
                """;

        assertThat(parser.parse(payload)).containsExactly(
                new RevisionSignal(1001L, 4L, true, 91L, 0),
                new RevisionSignal(1002L, 8L, false, 91L, 1));
    }

    @Test
    void ignores_ddl_and_unrelated_tables() {
        assertThat(parser.parse("""
                {"id":92,"database":"product_catalog","table":"products",
                 "isDdl":false,"type":"UPDATE","data":[{"id":"1001"}]}
                """)).isEmpty();
        assertThat(parser.parse("""
                {"id":93,"database":"product_catalog",
                 "table":"product_search_revision","isDdl":true,
                 "type":"ALTER","data":[]}
                """)).isEmpty();
    }

    @Test
    void rejects_malformed_json_and_missing_or_invalid_required_fields() {
        assertInvalid("not-json");
        assertInvalid(message("{\"revision\":\"1\",\"active\":\"1\"}"));
        assertInvalid(message("{\"product_id\":\"x\",\"revision\":\"1\",\"active\":\"1\"}"));
        assertInvalid(message("{\"product_id\":\"1\",\"revision\":\"x\",\"active\":\"1\"}"));
        assertInvalid(message("{\"product_id\":\"1\",\"revision\":\"1\",\"active\":\"maybe\"}"));
    }

    private void assertInvalid(String payload) {
        assertThatThrownBy(() -> parser.parse(payload))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private static String message(String row) {
        return "{\"id\":94,\"database\":\"product_catalog\","
                + "\"table\":\"product_search_revision\",\"isDdl\":false,\"data\":["
                + row + "]}";
    }
}
