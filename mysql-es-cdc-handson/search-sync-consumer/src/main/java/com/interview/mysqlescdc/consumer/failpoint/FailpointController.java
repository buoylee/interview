package com.interview.mysqlescdc.consumer.failpoint;

import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/internal/failpoints")
@ConditionalOnProperty(name = "lab.failpoints.enabled", havingValue = "true")
public final class FailpointController {
    private final FailpointRegistry registry;

    public FailpointController(FailpointRegistry registry) {
        this.registry = registry;
    }

    @PostMapping("/{name}/arm")
    public Map<String, Integer> arm(@PathVariable String name, @RequestParam(defaultValue = "1") int hits) {
        try {
            registry.arm(Failpoint.valueOf(name), hits);
            return list();
        } catch (IllegalArgumentException failure) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, failure.getMessage(), failure);
        }
    }

    @DeleteMapping
    public Map<String, Integer> clear() {
        registry.clear();
        return list();
    }

    @GetMapping
    public Map<String, Integer> list() {
        Map<String, Integer> response = new LinkedHashMap<>();
        registry.remaining().forEach((failpoint, remaining) -> response.put(failpoint.name(), remaining));
        return response;
    }
}
