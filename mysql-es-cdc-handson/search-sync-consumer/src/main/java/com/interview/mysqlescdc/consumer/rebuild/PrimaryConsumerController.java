package com.interview.mysqlescdc.consumer.rebuild;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/internal/rebuild/primary")
public final class PrimaryConsumerController {
    private final PrimaryConsumerControl control;
    public PrimaryConsumerController(PrimaryConsumerControl control) { this.control = control; }
    @PostMapping("/pause") public PrimaryConsumerStatus pause() { return control.pause(); }
    @PostMapping("/resume") public PrimaryConsumerStatus resume() { return control.resume(); }
    @GetMapping("/status") public PrimaryConsumerStatus status() { return control.status(); }
}
