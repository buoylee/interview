package com.interview.mysqlescdc.verifier.run;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.Map;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import com.interview.mysqlescdc.verifier.repair.RepairReport;
import com.interview.mysqlescdc.verifier.repair.RepairService;

class ReconciliationControllerTest {
    private VerificationRunService runs;
    private RepairService repairs;
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        runs = mock(VerificationRunService.class);
        repairs = mock(RepairService.class);
        mvc = MockMvcBuilders.standaloneSetup(
                new ReconciliationController(runs, repairs, "products_write", 200)).build();
    }

    @Test
    void post_runs_starts_verification_with_requested_target_and_page_size() throws Exception {
        UUID runId = UUID.randomUUID();
        VerificationRequest request = new VerificationRequest("products_read", 25);
        when(runs.run(request)).thenReturn(new VerificationRunReport(
                runId, "products_read", VerificationRunStatus.PASS,
                8, 8L, 2, 2, 0, Map.of(), null, null));

        mvc.perform(post("/internal/reconciliation/runs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"target\":\"products_read\",\"pageSize\":25}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.runId").value(runId.toString()))
                .andExpect(jsonPath("$.status").value("PASS"));

        verify(runs).run(request);
    }

    @Test
    void post_repair_uses_run_identifier_from_path() throws Exception {
        UUID runId = UUID.randomUUID();
        when(repairs.repair(runId)).thenReturn(
                new RepairReport(runId, 9, 9, 3, 0, 0, 0, true, true));

        mvc.perform(post("/internal/reconciliation/runs/{runId}/repair", runId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.runId").value(runId.toString()))
                .andExpect(jsonPath("$.repaired").value(true));

        verify(repairs).repair(runId);
    }

    @Test
    void rejected_request_returns_bounded_conflict_body() throws Exception {
        String oversized = "x".repeat(700);
        when(runs.run(new VerificationRequest("products_write", 200)))
                .thenThrow(new IllegalStateException(oversized));

        mvc.perform(post("/internal/reconciliation/runs"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error").value("IllegalStateException"))
                .andExpect(jsonPath("$.message").value("x".repeat(512)));
    }
}
