package com.interview.mysqlescdc.consumer.rebuild;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/internal/rebuild/shadow")
public final class ShadowReplayController {
    private final ShadowReplayService service;
    public ShadowReplayController(ShadowReplayService service) { this.service = service; }
    @PostMapping public ShadowReplayStatus start(@RequestBody ShadowReplayRequest request) { return service.start(request); }
    @GetMapping("/{runId}") public ShadowReplayStatus status(@PathVariable java.util.UUID runId) { return service.status(runId); }
    @DeleteMapping("/{runId}") public ShadowReplayStatus stop(@PathVariable java.util.UUID runId) { return service.stop(runId); }
}
