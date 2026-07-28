package com.interview.mysqlescdc.product.application;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;

@Component
public final class ProductWriteGate {
    private final JdbcClient jdbc;
    public ProductWriteGate(JdbcClient jdbc) { this.jdbc = jdbc; }
    public void assertOpenForMutation() {
        GateRow row = jdbc.sql("""
                SELECT closed, BIN_TO_UUID(owner_run_id) owner_run_id, reason
                FROM product_write_gate WHERE singleton_id=1 FOR SHARE
                """).query(GateRow.class).single();
        if (row.closed()) throw new WriteGateClosedException(row.ownerRunId(), row.reason());
    }
    record GateRow(boolean closed, String ownerRunId, String reason) {}
}
