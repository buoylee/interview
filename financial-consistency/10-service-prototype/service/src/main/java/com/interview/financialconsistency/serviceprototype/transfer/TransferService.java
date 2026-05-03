package com.interview.financialconsistency.serviceprototype.transfer;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.financialconsistency.serviceprototype.account.AccountRecord;
import com.interview.financialconsistency.serviceprototype.account.AccountRepository;
import com.interview.financialconsistency.serviceprototype.idempotency.IdempotencyRepository;
import com.interview.financialconsistency.serviceprototype.ledger.LedgerRepository;
import com.interview.financialconsistency.serviceprototype.outbox.OutboxRepository;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TransferService {
    private static final String BUSINESS_TYPE = "TRANSFER";

    private final AccountRepository accountRepository;
    private final TransferRepository transferRepository;
    private final LedgerRepository ledgerRepository;
    private final IdempotencyRepository idempotencyRepository;
    private final OutboxRepository outboxRepository;
    private final ObjectMapper objectMapper;

    public TransferService(
            AccountRepository accountRepository,
            TransferRepository transferRepository,
            LedgerRepository ledgerRepository,
            IdempotencyRepository idempotencyRepository,
            OutboxRepository outboxRepository,
            ObjectMapper objectMapper) {
        this.accountRepository = accountRepository;
        this.transferRepository = transferRepository;
        this.ledgerRepository = ledgerRepository;
        this.idempotencyRepository = idempotencyRepository;
        this.outboxRepository = outboxRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public TransferResponse transfer(TransferRequest request) {
        TransferResponse validationFailure = validate(request);
        if (validationFailure != null) {
            return validationFailure;
        }

        BigDecimal amount;
        String requestHash;
        try {
            amount = request.amount().setScale(4, RoundingMode.UNNECESSARY);
            requestHash = requestHash(request);
        } catch (ArithmeticException ex) {
            return rejected("Amount must have exactly four decimal places");
        }

        TransferResponse accountValidationFailure = validateAccounts(request);
        if (accountValidationFailure != null) {
            return accountValidationFailure;
        }

        try {
            idempotencyRepository.insertProcessing(request.idempotencyKey(), requestHash, BUSINESS_TYPE);
        } catch (DuplicateKeyException ex) {
            return handleDuplicateRequest(request.idempotencyKey(), requestHash);
        }

        List<AccountRecord> lockedAccounts = lockAccounts(request.fromAccountId(), request.toAccountId());
        AccountRecord fromAccount = accountById(lockedAccounts, request.fromAccountId());
        TransferResponse lockedAccountValidationFailure = validateLockedAccounts(request, lockedAccounts);
        if (lockedAccountValidationFailure != null) {
            idempotencyRepository.markCompleted(
                    request.idempotencyKey(),
                    null,
                    "REJECTED",
                    409,
                    responseBody(lockedAccountValidationFailure));
            return lockedAccountValidationFailure;
        }

        String transferId = "T-" + UUID.randomUUID();
        if (fromAccount.availableBalance().compareTo(amount) < 0) {
            TransferResponse response = new TransferResponse(transferId, "FAILED", "Insufficient funds");
            transferRepository.insert(
                    transferId,
                    request.idempotencyKey(),
                    request.fromAccountId(),
                    request.toAccountId(),
                    request.currency(),
                    amount,
                    "FAILED",
                    "INSUFFICIENT_FUNDS");
            idempotencyRepository.markCompleted(
                    request.idempotencyKey(), transferId, "FAILED", 422, responseBody(response));
            return response;
        }

        transferRepository.insert(
                transferId,
                request.idempotencyKey(),
                request.fromAccountId(),
                request.toAccountId(),
                request.currency(),
                amount,
                "SUCCEEDED",
                null);
        ledgerRepository.insert(
                "L-" + UUID.randomUUID(),
                transferId,
                request.fromAccountId(),
                "DEBIT",
                request.currency(),
                amount,
                "TRANSFER");
        ledgerRepository.insert(
                "L-" + UUID.randomUUID(),
                transferId,
                request.toAccountId(),
                "CREDIT",
                request.currency(),
                amount,
                "TRANSFER");
        accountRepository.applyBalanceDelta(request.fromAccountId(), amount.negate());
        accountRepository.applyBalanceDelta(request.toAccountId(), amount);
        outboxRepository.insertPending(
                "M-" + UUID.randomUUID(),
                BUSINESS_TYPE,
                transferId,
                "TransferSucceeded",
                outboxPayload(transferId, request, amount));

        TransferResponse response = new TransferResponse(transferId, "SUCCEEDED", "Transfer succeeded");
        idempotencyRepository.markCompleted(
                request.idempotencyKey(), transferId, "SUCCEEDED", 200, responseBody(response));
        return response;
    }

    private TransferResponse validate(TransferRequest request) {
        if (request == null) {
            return rejected("Request is required");
        }
        if (isBlank(request.idempotencyKey())) {
            return rejected("Idempotency key is required");
        }
        if (isBlank(request.fromAccountId()) || isBlank(request.toAccountId())) {
            return rejected("Both accounts are required");
        }
        if (request.fromAccountId().equals(request.toAccountId())) {
            return rejected("Transfer accounts must be different");
        }
        if (request.amount() == null || request.amount().compareTo(BigDecimal.ZERO) <= 0) {
            return rejected("Amount must be positive");
        }
        if (request.currency() == null || !request.currency().matches("[A-Z]{3}")) {
            return rejected("Currency must be a 3-letter code");
        }
        return null;
    }

    private TransferResponse validateAccounts(TransferRequest request) {
        AccountRecord fromAccount = accountRepository.findById(request.fromAccountId()).orElse(null);
        if (fromAccount == null) {
            return rejected("Source account does not exist");
        }
        AccountRecord toAccount = accountRepository.findById(request.toAccountId()).orElse(null);
        if (toAccount == null) {
            return rejected("Target account does not exist");
        }
        if (!request.currency().equals(fromAccount.currency()) || !request.currency().equals(toAccount.currency())) {
            return rejected("Transfer currency must match both accounts");
        }
        return null;
    }

    private TransferResponse validateLockedAccounts(TransferRequest request, List<AccountRecord> lockedAccounts) {
        AccountRecord fromAccount = accountById(lockedAccounts, request.fromAccountId());
        AccountRecord toAccount = accountById(lockedAccounts, request.toAccountId());
        if (!request.currency().equals(fromAccount.currency()) || !request.currency().equals(toAccount.currency())) {
            return rejected("Transfer currency must match both accounts");
        }
        return null;
    }

    private TransferResponse handleDuplicateRequest(String idempotencyKey, String requestHash) {
        Map<String, Object> record = idempotencyRepository.findForUpdate(idempotencyKey).orElseThrow();
        if (!requestHash.equals(record.get("request_hash"))) {
            return rejected("Idempotency key was already used for a different request");
        }
        String status = (String) record.get("status");
        if (("SUCCEEDED".equals(status) || "FAILED".equals(status) || "REJECTED".equals(status))
                && record.get("response_body") != null) {
            return storedResponse((String) record.get("response_body"));
        }
        return rejected("Request is already processing");
    }

    private List<AccountRecord> lockAccounts(String fromAccountId, String toAccountId) {
        return List.of(fromAccountId, toAccountId).stream()
                .sorted(Comparator.naturalOrder())
                .map(accountRepository::findForUpdate)
                .toList();
    }

    private AccountRecord accountById(List<AccountRecord> accounts, String accountId) {
        return accounts.stream()
                .filter(account -> account.accountId().equals(accountId))
                .findFirst()
                .orElseThrow();
    }

    private String requestHash(TransferRequest request) {
        String canonical = request.fromAccountId() + "|"
                + request.toAccountId() + "|"
                + request.currency() + "|"
                + request.amount().setScale(4, RoundingMode.UNNECESSARY).toPlainString();
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(canonical.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 digest is unavailable", ex);
        }
    }

    private TransferResponse rejected(String message) {
        return new TransferResponse(null, "REJECTED", message);
    }

    private String responseBody(TransferResponse response) {
        try {
            return objectMapper.writeValueAsString(response);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Failed to serialize transfer response", ex);
        }
    }

    private TransferResponse storedResponse(String responseBody) {
        try {
            return objectMapper.readValue(responseBody, TransferResponse.class);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Failed to deserialize transfer response", ex);
        }
    }

    private String outboxPayload(String transferId, TransferRequest request, BigDecimal amount) {
        return "{\"transferId\":\"" + transferId + "\","
                + "\"fromAccountId\":\"" + request.fromAccountId() + "\","
                + "\"toAccountId\":\"" + request.toAccountId() + "\","
                + "\"currency\":\"" + request.currency() + "\","
                + "\"amount\":\"" + amount.toPlainString() + "\"}";
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
