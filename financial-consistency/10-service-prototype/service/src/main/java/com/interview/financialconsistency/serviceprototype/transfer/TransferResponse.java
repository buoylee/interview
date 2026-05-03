package com.interview.financialconsistency.serviceprototype.transfer;

public record TransferResponse(
        String transferId,
        String status,
        String message) {
}
