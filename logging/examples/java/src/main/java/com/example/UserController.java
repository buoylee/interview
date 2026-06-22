package com.example;

import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class UserController {
    private static final Logger log = LoggerFactory.getLogger(UserController.class);

    private final UserService service;

    public UserController(UserService service) {
        this.service = service;
    }

    @GetMapping("/users/{id}")
    public Map<String, Object> getUser(@PathVariable long id) {
        if (id <= 0) {
            log.info("invalid user id, rejecting, id={}", id); // 01:正常業務,INFO 不是 ERROR
            throw new InvalidIdException(id);                   // → 由 GlobalExceptionHandler 回 400
        }
        Map<String, Object> user = service.fetch(id);
        log.info("user fetched, id={}", id); // 02:業務里程碑
        return user;
    }
}
