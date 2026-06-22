package com.example;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

/** 驗證:打四種請求,確認 status 正確;同時觸發 JSON 結構化日誌輸出到 stdout。 */
@SpringBootTest
@AutoConfigureMockMvc
class AppTests {

    @Autowired
    private MockMvc mvc;

    @Test
    void endpoints() throws Exception {
        mvc.perform(get("/users/42").header("X-Request-ID", "req-42"))
                .andExpect(status().isOk());
        mvc.perform(get("/users/0").header("X-Request-ID", "req-0"))
                .andExpect(status().isBadRequest());
        mvc.perform(get("/users/13").header("X-Request-ID", "req-13"))
                .andExpect(status().isNotFound());
        mvc.perform(get("/users/99").header("X-Request-ID", "req-99"))
                .andExpect(status().isInternalServerError());
    }
}
