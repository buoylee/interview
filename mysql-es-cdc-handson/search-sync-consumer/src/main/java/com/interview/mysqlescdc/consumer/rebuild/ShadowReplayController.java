package com.interview.mysqlescdc.consumer.rebuild;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/internal/rebuild/shadow")
public final class ShadowReplayController {
    private final ShadowReplayService service;
    public ShadowReplayController(ShadowReplayService service) { this.service = service; }
    @PostMapping("/start") public ShadowReplayStatus start(@RequestBody ShadowReplayRequest request) { return service.start(request); }
    @GetMapping("/status") public ShadowReplayStatus status() { return service.status(); }
    @PostMapping("/stop") public ShadowReplayStatus stop() { return service.stop(); }
}
