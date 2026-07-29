package com.interview.mysqlescdc.verifier.lab;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.server.ResponseStatusException;

class ScenarioEventControllerTest {
    @Test void rejects_non_loopback_before_the_producer_can_connect() {
        var request = new MockHttpServletRequest();
        request.setRemoteAddr("192.0.2.10");
        var controller = new ScenarioEventController(new ScenarioEventProducer("localhost:1", true));
        var event = new ScenarioEventRequest("product-search-revisions", 1,
                "{\"database\":\"product_catalog\",\"table\":\"product_search_revision\",\"isDdl\":false,\"type\":\"UPDATE\",\"data\":[{\"product_id\":\"1001\",\"revision\":\"1\",\"active\":\"1\"}]}");

        assertThatThrownBy(() -> controller.send(event, request))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("403 FORBIDDEN");
    }
}
