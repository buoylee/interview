package com.interview.mysqlescdc.verifier.rebuild;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice(assignableTypes = RebuildController.class)
final class RebuildApiExceptionHandler {
    @ExceptionHandler({IllegalArgumentException.class, IllegalStateException.class})
    ResponseEntity<Map<String,String>> rejected(RuntimeException failure) {
        String message = failure.getMessage() == null ? "rebuild request rejected" : failure.getMessage();
        if (message.length() > 256) message = message.substring(0, 256);
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(Map.of("code", "REBUILD_REJECTED", "message", message));
    }
}
