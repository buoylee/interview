package com.interview.mysqlescdc.verifier.api;

import java.util.Map;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.interview.mysqlescdc.verifier.status.PipelineConditionStore;
import com.interview.mysqlescdc.verifier.status.PipelineStatusReport;
import com.interview.mysqlescdc.verifier.status.PipelineStatusService;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.json.JsonMapper;

@RestController
@RequestMapping("/internal/pipeline")
public final class PipelineStatusController {
    private final PipelineStatusService status;
    private final PipelineConditionStore conditions;
    private final JsonMapper json = JsonMapper.builder().build();

    public PipelineStatusController(
            PipelineStatusService status, PipelineConditionStore conditions) {
        this.status = status;
        this.conditions = conditions;
    }

    @GetMapping("/status")
    public PipelineStatusReport status() {
        return status.current();
    }

    @PutMapping("/conditions/LOG_GAP")
    public ResponseEntity<Map<String, Object>> activateLogGap(
            @RequestBody(required = false) Map<String, Object> details) {
        conditions.activate("LOG_GAP", boundedJson(details == null ? Map.of() : details));
        return ResponseEntity.ok(Map.of("condition", "LOG_GAP", "active", true));
    }

    @DeleteMapping("/conditions/LOG_GAP")
    public ResponseEntity<Map<String, Object>> clearLogGap(
            @RequestParam UUID rebuildRunId) {
        if (!conditions.clearLogGap(rebuildRunId)) {
            throw new IllegalStateException("LOG_GAP requires a proven successful rebuild");
        }
        return ResponseEntity.ok(Map.of("condition", "LOG_GAP", "active", false));
    }

    @ExceptionHandler({IllegalArgumentException.class, IllegalStateException.class})
    public ResponseEntity<Map<String, String>> boundedFailure(RuntimeException exception) {
        String message = exception.getMessage() == null ? "pipeline status request failed"
                : exception.getMessage();
        if (message.length() > 512) message = message.substring(0, 512);
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(Map.of("error", exception.getClass().getSimpleName(), "message", message));
    }

    private String boundedJson(Map<String, Object> details) {
        try {
            String value = json.writeValueAsString(details);
            if (value.length() > 512) {
                throw new IllegalArgumentException("condition details exceed 512 characters");
            }
            return value;
        } catch (JacksonException exception) {
            throw new IllegalArgumentException("condition details are not JSON serializable", exception);
        }
    }
}
