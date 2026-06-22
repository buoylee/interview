package com.example;

/** 可預期的業務狀況(參數非法)—— 不是 ERROR(01)。 */
public class InvalidIdException extends RuntimeException {
    private final long id;

    public InvalidIdException(long id) {
        super("invalid id: " + id);
        this.id = id;
    }

    public long getId() {
        return id;
    }
}
