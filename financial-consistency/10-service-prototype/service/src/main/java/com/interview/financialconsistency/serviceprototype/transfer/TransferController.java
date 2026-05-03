package com.interview.financialconsistency.serviceprototype.transfer;

import java.math.BigDecimal;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/transfers")
public class TransferController {
    private final TransferService transferService;

    public TransferController(TransferService transferService) {
        this.transferService = transferService;
    }

    @PostMapping
    ResponseEntity<TransferResponse> create(
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @RequestBody TransferHttpRequest body) {
        if (idempotencyKey == null || idempotencyKey.isBlank()) {
            return ResponseEntity.badRequest()
                    .body(new TransferResponse(null, "REJECTED", "Idempotency-Key header is required"));
        }

        TransferResponse response = transferService.transfer(new TransferRequest(
                idempotencyKey,
                body.fromAccountId(),
                body.toAccountId(),
                body.currency(),
                body.amount()));

        return switch (response.status()) {
            case "SUCCEEDED" -> ResponseEntity.status(201).body(response);
            case "FAILED" -> ResponseEntity.unprocessableEntity().body(response);
            case "REJECTED" -> ResponseEntity.status(409).body(response);
            default -> ResponseEntity.internalServerError().body(response);
        };
    }

    public record TransferHttpRequest(
            String fromAccountId,
            String toAccountId,
            String currency,
            BigDecimal amount) {
    }
}
