package com.interview.mysqlescdc.verifier.api;

import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;
import com.interview.mysqlescdc.verifier.status.PipelineConditionStore;
import com.interview.mysqlescdc.verifier.status.PipelineStatus;
import com.interview.mysqlescdc.verifier.status.PipelineStatusReport;
import com.interview.mysqlescdc.verifier.status.PipelineStatusService;

class PipelineStatusControllerTest {
    private PipelineStatusService service;
    private PipelineConditionStore conditions;
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        service = mock(PipelineStatusService.class);
        conditions = mock(PipelineConditionStore.class);
        mvc = MockMvcBuilders.standaloneSetup(
                new PipelineStatusController(service, conditions)).build();
    }

    @Test
    void exposes_status_from_evidence_service() throws Exception {
        UUID runId = UUID.randomUUID();
        Instant now = Instant.parse("2026-07-22T12:00:00Z");
        when(service.current()).thenReturn(new PipelineStatusReport(
                PipelineStatus.HEALTHY, 0, true, List.of(), 0, runId,
                VerificationRunStatus.PASS, 0, now.minusSeconds(2), Set.of(), now));

        mvc.perform(get("/internal/pipeline/status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.state").value("HEALTHY"))
                .andExpect(jsonPath("$.latestRunId").value(runId.toString()))
                .andExpect(jsonPath("$.kafkaLag").value(0));
    }

    @Test
    void log_gap_put_is_durable_idempotent_contract_with_bounded_json() throws Exception {
        mvc.perform(put("/internal/pipeline/conditions/LOG_GAP")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"reason\":\"operator_observed\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.active").value(true));

        verify(conditions).activate(org.mockito.ArgumentMatchers.eq("LOG_GAP"),
                argThat(json -> json.length() <= 512 && json.contains("operator_observed")));
    }

    @Test
    void log_gap_delete_refuses_unproven_rebuild() throws Exception {
        UUID rebuildRunId = UUID.randomUUID();
        when(conditions.clearLogGap(rebuildRunId)).thenReturn(false);

        mvc.perform(delete("/internal/pipeline/conditions/LOG_GAP")
                        .queryParam("rebuildRunId", rebuildRunId.toString()))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.message").value(
                        "LOG_GAP requires a proven successful rebuild"));
    }
}
