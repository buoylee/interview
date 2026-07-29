package com.interview.mysqlescdc.verifier.rebuild;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice(assignableTypes = RebuildController.class)
final class RebuildApiExceptionHandler {
    @ExceptionHandler(IllegalArgumentException.class)
    ResponseEntity<Map<String,String>> invalid(IllegalArgumentException failure) {
        return response(HttpStatus.BAD_REQUEST,failure);
    }
    @ExceptionHandler(IllegalStateException.class)
    ResponseEntity<Map<String,String>> rejected(IllegalStateException failure) {
        return response(HttpStatus.CONFLICT,failure);
    }
    private ResponseEntity<Map<String,String>> response(HttpStatus status,RuntimeException failure) {
        String message = failure.getMessage() == null ? "rebuild request rejected" : failure.getMessage();
        if (message.length() > 256) message = message.substring(0, 256);
        return ResponseEntity.status(status)
                .body(Map.of("code", "REBUILD_REJECTED", "message", message));
    }
}
