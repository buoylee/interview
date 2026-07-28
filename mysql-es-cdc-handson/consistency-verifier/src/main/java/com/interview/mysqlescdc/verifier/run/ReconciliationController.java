package com.interview.mysqlescdc.verifier.run;

import java.util.Map;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.interview.mysqlescdc.verifier.repair.RepairReport;
import com.interview.mysqlescdc.verifier.repair.RepairService;

@RestController
@RequestMapping("/internal/reconciliation/runs")
public final class ReconciliationController {
    private final VerificationRunService runs;
    private final RepairService repairs;
    private final String defaultTarget;
    private final int defaultPageSize;

    public ReconciliationController(
            VerificationRunService runs,
            RepairService repairs,
            @Value("${verification.target:products_write}") String defaultTarget,
            @Value("${verification.page-size:200}") int defaultPageSize) {
        this.runs = runs;
        this.repairs = repairs;
        this.defaultTarget = defaultTarget;
        this.defaultPageSize = defaultPageSize;
    }

    @PostMapping
    public VerificationRunReport run(
            @RequestBody(required = false) VerificationRequest request) {
        VerificationRequest effective = request == null
                ? new VerificationRequest(defaultTarget, defaultPageSize)
                : request;
        return runs.run(effective);
    }

    @PostMapping("/{runId}/repair")
    public RepairReport repair(@PathVariable UUID runId) {
        return repairs.repair(runId);
    }

    @ExceptionHandler({IllegalArgumentException.class, IllegalStateException.class})
    public ResponseEntity<Map<String, String>> boundedFailure(RuntimeException exception) {
        String message = exception.getMessage() == null ? "reconciliation request failed"
                : exception.getMessage();
        if (message.length() > 512) message = message.substring(0, 512);
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(Map.of("error", exception.getClass().getSimpleName(), "message", message));
    }
}
