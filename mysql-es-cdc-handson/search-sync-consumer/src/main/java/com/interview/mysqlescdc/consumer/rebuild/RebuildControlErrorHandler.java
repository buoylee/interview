package com.interview.mysqlescdc.consumer.rebuild;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestControllerAdvice(assignableTypes = {ShadowReplayController.class, PrimaryConsumerController.class})
public final class RebuildControlErrorHandler {
    @ExceptionHandler({IllegalArgumentException.class, IllegalStateException.class})
    @ResponseStatus(HttpStatus.CONFLICT)
    public Map<String,String> bounded(RuntimeException failure) {
        return Map.of("failureClass", failure.getClass().getSimpleName());
    }
    @ExceptionHandler(ShadowRunNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Map<String,String> missing(ShadowRunNotFoundException failure) { return Map.of("failureClass", failure.getClass().getSimpleName()); }
}
