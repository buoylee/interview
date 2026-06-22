package com.example;

/** 可預期的業務狀況 —— 不是 ERROR(01)。 */
public class UserNotFoundException extends RuntimeException {
    private final long id;

    public UserNotFoundException(long id) {
        super("user not found: " + id);
        this.id = id;
    }

    public long getId() {
        return id;
    }
}
