package com.example;

import java.io.IOException;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/** 02/03:請求邊界過濾器 —— 設定 MDC request_id、記進出。 */
@Component
public class RequestLoggingFilter extends OncePerRequestFilter {
    private static final Logger log = LoggerFactory.getLogger(RequestLoggingFilter.class);

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        String rid = req.getHeader("X-Request-ID");
        if (rid == null || rid.isBlank()) {
            rid = UUID.randomUUID().toString().substring(0, 12);
        }
        MDC.put("requestId", rid); // 03:之後這個請求的每一行日誌都自動帶 requestId
        res.setHeader("X-Request-ID", rid);

        long start = System.nanoTime();
        log.info("request started, method={} path={}", req.getMethod(), req.getRequestURI());
        try {
            chain.doFilter(req, res);
        } finally {
            log.info("request finished, status={} latency_ms={}",
                    res.getStatus(), (System.nanoTime() - start) / 1_000_000);
            MDC.clear(); // 03 🔬:執行緒池會重用執行緒,一定要清,否則下個請求串味
        }
    }
}
