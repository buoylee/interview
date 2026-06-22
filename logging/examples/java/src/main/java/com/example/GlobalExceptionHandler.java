package com.example;

import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import jakarta.servlet.http.HttpServletRequest;

/** 04:全域異常處理器 —— log-or-throw 的「頂層」,異常在這裡記一次。 */
@RestControllerAdvice
public class GlobalExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(InvalidIdException.class)
    public ResponseEntity<Map<String, Object>> onInvalid(InvalidIdException e) {
        // 已在 controller 記過 info,這裡只回應,不重複記(避免 cascade)
        return ResponseEntity.badRequest().body(Map.of("error", "invalid id"));
    }

    @ExceptionHandler(UserNotFoundException.class)
    public ResponseEntity<Map<String, Object>> onNotFound(UserNotFoundException e) {
        log.info("user not found, id={}", e.getId()); // 01:正常業務,INFO 不是 ERROR
        return ResponseEntity.status(404).body(Map.of("error", "not found"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> onError(Exception e, HttpServletRequest req) {
        // 唯一記「未捕獲異常」完整堆疊+cause 的地方;e 當最後一個參數(不是塞進字串)
        log.error("unhandled error, path={}", req.getRequestURI(), e);
        return ResponseEntity.status(500).body(Map.of("error", "internal"));
    }
}
