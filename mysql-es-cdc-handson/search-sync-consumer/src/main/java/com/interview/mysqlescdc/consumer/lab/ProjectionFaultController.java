package com.interview.mysqlescdc.consumer.lab;

import java.util.Map;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/internal/lab/projection-fault")
@ConditionalOnProperty(name = "lab.failpoints.enabled", havingValue = "true")
public final class ProjectionFaultController {
    private final ProjectionFaultRegistry registry;

    public ProjectionFaultController(ProjectionFaultRegistry registry) {
        this.registry = registry;
    }

    @PutMapping("/{mode}")
    public Map<String, String> arm(@PathVariable ProjectionFaultMode mode,
            @RequestParam(required = false) Long productId) {
        ProjectionFaultMode armed = productId == null ? registry.arm(mode) : registry.arm(mode, productId);
        return response(armed);
    }

    Map<String, String> arm(ProjectionFaultMode mode) { return arm(mode, null); }

    @DeleteMapping
    public Map<String, String> clear() {
        return response(registry.clear());
    }

    private Map<String, String> response(ProjectionFaultMode mode) {
        return Map.of("fault", mode.name());
    }
}
