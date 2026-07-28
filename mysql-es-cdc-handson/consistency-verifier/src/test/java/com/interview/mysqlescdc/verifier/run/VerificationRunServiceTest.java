package com.interview.mysqlescdc.verifier.run;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

import com.interview.mysqlescdc.verifier.diff.ReconciliationEngine;
import com.interview.mysqlescdc.verifier.source.ExpectedDocumentReader;
import com.interview.mysqlescdc.verifier.source.ExpectedPage;
import com.interview.mysqlescdc.verifier.source.SourceWatermarkReader;
import com.interview.mysqlescdc.verifier.target.IndexedDocumentReader;
import com.interview.mysqlescdc.verifier.target.IndexedPage;
import com.interview.mysqlescdc.verifier.target.TargetCursor;

class VerificationRunServiceTest {
    private final SourceWatermarkReader watermark = mock(SourceWatermarkReader.class);
    private final ExpectedDocumentReader source = mock(ExpectedDocumentReader.class);
    private final IndexedDocumentReader target = mock(IndexedDocumentReader.class);
    private final VerificationRunStore store = mock(VerificationRunStore.class);
    private final TargetCursor cursor = mock(TargetCursor.class);
    private final VerificationRunService service = new VerificationRunService(
            watermark, source, target, new ReconciliationEngine(), store);

    @Test
    void running_is_persisted_before_scan_and_stable_zero_diff_becomes_pass_after_pit_close() {
        when(watermark.current()).thenReturn(90L, 90L);
        when(target.open("products_write")).thenReturn(cursor);
        when(source.readAfter(0, 2)).thenReturn(new ExpectedPage(List.of(), 0, true));
        when(target.readAfter(cursor, null, 2)).thenReturn(new IndexedPage(List.of(), null, true));

        VerificationRunReport report = service.run(new VerificationRequest("products_write", 2));

        assertThat(report.status()).as(report.toString()).isEqualTo(VerificationRunStatus.PASS);
        assertThat(report.sourceWatermarkStart()).isEqualTo(90);
        assertThat(report.sourceWatermarkEnd()).isEqualTo(90);
        InOrder order = inOrder(store, target, cursor, watermark);
        order.verify(watermark).current();
        order.verify(store).createRunning(eq(report.runId()), eq("products_write"), eq(90L));
        order.verify(target).open("products_write");
        order.verify(cursor).close();
        order.verify(watermark).current();
        order.verify(store).complete(eq(report.runId()), eq(VerificationRunStatus.PASS),
                eq(90L), any());
    }

    @Test
    void moving_source_is_inconclusive_even_when_observed_diff_is_zero() {
        when(watermark.current()).thenReturn(100L, 101L);
        when(target.open("products_write")).thenReturn(cursor);
        when(source.readAfter(0, 2)).thenReturn(new ExpectedPage(List.of(), 0, true));
        when(target.readAfter(cursor, null, 2)).thenReturn(new IndexedPage(List.of(), null, true));

        VerificationRunReport report = service.run(new VerificationRequest("products_write", 2));

        assertThat(report.status()).as(report.toString())
                .isEqualTo(VerificationRunStatus.INCONCLUSIVE);
        assertThat(report.differenceCount()).isZero();
        verify(store).complete(eq(report.runId()), eq(VerificationRunStatus.INCONCLUSIVE),
                eq(101L), any());
    }

    @Test
    void scan_exception_closes_pit_and_persists_failed_with_bounded_diagnostics() {
        when(watermark.current()).thenReturn(110L);
        when(target.open("products_write")).thenReturn(cursor);
        when(source.readAfter(0, 2)).thenThrow(new IllegalStateException("x".repeat(900)));

        VerificationRunReport report = service.run(new VerificationRequest("products_write", 2));

        assertThat(report.status()).isEqualTo(VerificationRunStatus.FAILED);
        assertThat(report.failureMessage()).hasSizeLessThanOrEqualTo(512);
        verify(cursor).close();
        verify(store).fail(eq(report.runId()), eq("IllegalStateException"),
                eq(report.failureMessage()));
    }
}
