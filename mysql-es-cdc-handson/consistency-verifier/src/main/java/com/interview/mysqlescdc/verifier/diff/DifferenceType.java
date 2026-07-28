package com.interview.mysqlescdc.verifier.diff;

public enum DifferenceType {
    MISSING,
    EXTRA,
    MODIFIED,
    STALE,
    FUTURE_REVISION,
    TOMBSTONE_MISMATCH,
    VERSION_METADATA_MISMATCH
}
