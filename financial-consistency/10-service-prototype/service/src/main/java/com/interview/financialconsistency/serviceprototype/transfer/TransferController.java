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
            return badRequest("Idempotency-Key header is required");
        }
        TransferResponse validationFailure = validate(body);
        if (validationFailure != null) {
            return ResponseEntity.badRequest().body(validationFailure);
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

    private TransferResponse validate(TransferHttpRequest body) {
        if (body == null) {
            return rejected("Request body is required");
        }
        if (isBlank(body.fromAccountId()) || isBlank(body.toAccountId())) {
            return rejected("Both accounts are required");
        }
        if (body.fromAccountId().equals(body.toAccountId())) {
            return rejected("Transfer accounts must be different");
        }
        if (body.amount() == null || body.amount().compareTo(BigDecimal.ZERO) <= 0) {
            return rejected("Amount must be positive");
        }
        if (body.currency() == null || !body.currency().matches("[A-Z]{3}")) {
            return rejected("Currency must be a 3-letter code");
        }
        return null;
    }

    private ResponseEntity<TransferResponse> badRequest(String message) {
        return ResponseEntity.badRequest().body(rejected(message));
    }

    private TransferResponse rejected(String message) {
        return new TransferResponse(null, "REJECTED", message);
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    public record TransferHttpRequest(
            String fromAccountId,
            String toAccountId,
            String currency,
            BigDecimal amount) {
    }
}
