package com.interview.financialconsistency.codelab.model;

public enum FactType {
    LEDGER_POSTING,
    IDEMPOTENCY_RECORD,
    LOCAL_STATE,
    EXTERNAL_RESULT,
    OUTBOX_RECORD,
    OUTBOX_PUBLISHED,
    MESSAGE_HANDLED,
    BUSINESS_EFFECT,
    MANUAL_APPROVAL,
    MANUAL_REPAIR,
    MANUAL_REVIEW,
    SUPPLIER_RESULT,
    TCC_STAGE
}
