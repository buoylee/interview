package com.interview.mysqlescdc.verifier.run;

import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;

import com.interview.mysqlescdc.verifier.diff.ConsistencyReport;
import com.interview.mysqlescdc.verifier.diff.ReconciliationEngine;
import com.interview.mysqlescdc.verifier.diff.VerificationInput;
import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.source.ExpectedDocumentReader;
import com.interview.mysqlescdc.verifier.source.ExpectedPage;
import com.interview.mysqlescdc.verifier.source.SourceWatermarkReader;
import com.interview.mysqlescdc.verifier.target.IndexedDocument;
import com.interview.mysqlescdc.verifier.target.IndexedDocumentReader;
import com.interview.mysqlescdc.verifier.target.IndexedPage;
import com.interview.mysqlescdc.verifier.target.SearchAfterToken;
import com.interview.mysqlescdc.verifier.target.TargetCursor;
import com.interview.mysqlescdc.verifier.status.ReconciliationMetrics;

@Service
public final class VerificationRunService {
    private final SourceWatermarkReader watermark;
    private final ExpectedDocumentReader source;
    private final IndexedDocumentReader target;
    private final ReconciliationEngine engine;
    private final VerificationRunStore store;
    private ReconciliationMetrics metrics;

    public VerificationRunService(
            SourceWatermarkReader watermark,
            ExpectedDocumentReader source,
            IndexedDocumentReader target,
            ReconciliationEngine engine,
            VerificationRunStore store) {
        this.watermark = watermark;
        this.source = source;
        this.target = target;
        this.engine = engine;
        this.store = store;
    }

    public VerificationRunReport run(VerificationRequest request) {
        UUID runId = UUID.randomUUID();
        long start = watermark.current();
        store.createRunning(runId, request.target(), start);
        try {
            ConsistencyReport observed;
            try (TargetCursor cursor = target.open(request.target())) {
                observed = engine.compare(new VerificationInput(
                        runId, start, start,
                        new ExpectedIterator(source, request.pageSize()),
                        new IndexedIterator(target, cursor, request.pageSize()),
                        difference -> store.appendDifference(runId, difference)));
            }
            long end = watermark.current();
            VerificationRunStatus status = start != end
                    ? VerificationRunStatus.INCONCLUSIVE
                    : observed.differenceCount() == 0
                            ? VerificationRunStatus.PASS
                            : VerificationRunStatus.DIFF;
            ConsistencyReport finalReport = new ConsistencyReport(
                    runId, start, end, observed.expectedCount(), observed.actualCount(),
                    observed.differenceCount(), observed.counts(), start == end);
            store.complete(runId, status, end, finalReport);
            if (metrics != null) metrics.recordRun(status, finalReport.counts());
            return report(request.target(), status, finalReport, null, null);
        } catch (RuntimeException exception) {
            String failureClass = bounded(exception.getClass().getSimpleName(), 64);
            String failureMessage = bounded(exception.getMessage(), 512);
            store.fail(runId, failureClass, failureMessage);
            if (metrics != null) {
                metrics.recordRun(VerificationRunStatus.FAILED, Collections.emptyMap());
            }
            return new VerificationRunReport(
                    runId, request.target(), VerificationRunStatus.FAILED, start, null,
                    0, 0, 0, Collections.emptyMap(), failureClass, failureMessage);
        }
    }

    @Autowired
    void setMetrics(ReconciliationMetrics metrics) {
        this.metrics = metrics;
    }

    private VerificationRunReport report(
            String targetName,
            VerificationRunStatus status,
            ConsistencyReport report,
            String failureClass,
            String failureMessage) {
        return new VerificationRunReport(
                report.runId(), targetName, status,
                report.sourceWatermarkStart(), report.sourceWatermarkEnd(),
                report.expectedCount(), report.actualCount(), report.differenceCount(),
                report.counts(), failureClass, failureMessage);
    }

    private static String bounded(String value, int maximum) {
        String safe = value == null || value.isBlank() ? "unspecified failure" : value;
        return safe.length() <= maximum ? safe : safe.substring(0, maximum);
    }

    private static final class ExpectedIterator implements Iterator<ExpectedDocument> {
        private final ExpectedDocumentReader reader;
        private final int pageSize;
        private Iterator<ExpectedDocument> current = List.<ExpectedDocument>of().iterator();
        private long cursor;
        private boolean complete;

        private ExpectedIterator(ExpectedDocumentReader reader, int pageSize) {
            this.reader = reader;
            this.pageSize = pageSize;
        }

        @Override public boolean hasNext() {
            fill();
            return current.hasNext();
        }

        @Override public ExpectedDocument next() {
            if (!hasNext()) throw new NoSuchElementException();
            return current.next();
        }

        private void fill() {
            while (!current.hasNext() && !complete) {
                ExpectedPage page = reader.readAfter(cursor, pageSize);
                current = page.documents().iterator();
                cursor = page.nextExclusiveProductId();
                complete = page.complete();
            }
        }
    }

    private static final class IndexedIterator implements Iterator<IndexedDocument> {
        private final IndexedDocumentReader reader;
        private final TargetCursor cursor;
        private final int pageSize;
        private Iterator<IndexedDocument> current = List.<IndexedDocument>of().iterator();
        private SearchAfterToken token;
        private boolean complete;

        private IndexedIterator(
                IndexedDocumentReader reader, TargetCursor cursor, int pageSize) {
            this.reader = reader;
            this.cursor = cursor;
            this.pageSize = pageSize;
        }

        @Override public boolean hasNext() {
            fill();
            return current.hasNext();
        }

        @Override public IndexedDocument next() {
            if (!hasNext()) throw new NoSuchElementException();
            return current.next();
        }

        private void fill() {
            while (!current.hasNext() && !complete) {
                IndexedPage page = reader.readAfter(cursor, token, pageSize);
                current = page.documents().iterator();
                token = page.nextToken();
                complete = page.complete();
            }
        }
    }
}
