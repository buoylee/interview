package com.interview.mysqlescdc.verifier.rebuild;

import jakarta.servlet.http.HttpServletRequest;
import java.net.InetAddress;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/internal/rebuild")
public final class RebuildController {
    private final RebuildCoordinator coordinator;
    private final RebuildFailpointRegistry failpoints;
    private final CanalRecoveryService canalRecovery;

    public RebuildController(RebuildCoordinator coordinator, RebuildFailpointRegistry failpoints,
            CanalRecoveryService canalRecovery) {
        this.coordinator = coordinator;
        this.failpoints = failpoints;
        this.canalRecovery = canalRecovery;
    }

    @PostMapping("/runs")
    public ResponseEntity<RebuildStatus> start(@RequestBody Start body, HttpServletRequest request) {
        requireLoopback(request);
        UUID runId = body.runId() == null ? UUID.randomUUID() : body.runId();
        return ResponseEntity.ok(coordinator.start(new RebuildRequest(runId,
                body.reason() == null ? "MANUAL" : body.reason(),
                body.topic() == null ? "product-search-revisions" : body.topic(),
                body.pageSize() == null ? 200 : body.pageSize())));
    }

    @GetMapping("/runs/{runId}")
    public RebuildStatus status(@PathVariable UUID runId, HttpServletRequest request) {
        requireLoopback(request); return coordinator.status(runId);
    }

    @PostMapping("/runs/{runId}/resume")
    public RebuildStatus resume(@PathVariable UUID runId, HttpServletRequest request) {
        requireLoopback(request); return coordinator.resume(runId);
    }

    @PostMapping("/runs/{runId}/canal-recovery/start")
    public RebuildStatus recoveryStart(@PathVariable UUID runId, HttpServletRequest request) {
        requireLoopback(request); return coordinator.startCanalRecovery(runId,canalRecovery);
    }

    @PostMapping("/runs/{runId}/canal-recovery/complete")
    public RebuildStatus recoveryComplete(@PathVariable UUID runId,
            @RequestBody CanalRecoveryEvidence evidence, HttpServletRequest request) {
        requireLoopback(request);
        return coordinator.completeCanalRecovery(runId,evidence,canalRecovery);
    }

    @PutMapping("/failpoint/{point}")
    public Map<String, String> failpoint(@PathVariable RebuildFailpoint point,
            HttpServletRequest request) {
        requireLoopback(request); failpoints.set(point); return Map.of("failpoint", point.name());
    }

    @DeleteMapping("/failpoint")
    public Map<String, String> clear(HttpServletRequest request) {
        requireLoopback(request); failpoints.clear(); return Map.of("failpoint", "NONE");
    }

    private static void requireLoopback(HttpServletRequest request) {
        try {
            if (!InetAddress.getByName(request.getRemoteAddr()).isLoopbackAddress()) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "rebuild API is loopback-only");
            }
        } catch (java.net.UnknownHostException invalidAddress) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "rebuild API is loopback-only");
        }
    }

    public record Start(UUID runId, String reason, String topic, Integer pageSize) {}
}
