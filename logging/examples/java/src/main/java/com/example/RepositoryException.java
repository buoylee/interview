package com.example;

/** 不可預期的基礎設施失敗 —— 會冒泡到頂層被記成 ERROR。 */
public class RepositoryException extends RuntimeException {
    public RepositoryException(String message, Throwable cause) {
        super(message, cause); // 保留 cause chain(對應 04)
    }
}
