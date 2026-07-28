package com.interview.mysqlescdc.verifier.source;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public final class JdbcSourceWatermarkReader implements SourceWatermarkReader {
    private final JdbcClient jdbc;

    public JdbcSourceWatermarkReader(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public long current() {
        long value = jdbc.sql("SELECT value FROM source_change_watermark WHERE singleton_id = 1")
                .query(Long.class)
                .single();
        if (value < 0) {
            throw new IllegalStateException("source watermark must be non-negative");
        }
        return value;
    }
}
