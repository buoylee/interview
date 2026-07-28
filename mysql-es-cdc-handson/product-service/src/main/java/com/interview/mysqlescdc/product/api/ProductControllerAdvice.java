package com.interview.mysqlescdc.product.api;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import com.interview.mysqlescdc.product.application.WriteGateClosedException;

@RestControllerAdvice
public final class ProductControllerAdvice {
    @ExceptionHandler(WriteGateClosedException.class)
    @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)
    Map<String,Object> paused() { return Map.of("code", "PRODUCT_WRITES_PAUSED", "retryable", true); }
}
