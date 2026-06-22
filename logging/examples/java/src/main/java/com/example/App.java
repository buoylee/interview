package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Spring Boot 生產級日誌範例 —— 把 logging/ 六章紀律組裝在一個服務裡。
 *
 * 端點:GET /users/{id}
 *   id <= 0  → 參數非法,記 INFO(正常業務,不是 ERROR),回 400
 *   id == 13 → 查無此人,記 INFO(正常業務),回 404
 *   id == 99 → 模擬下游故障,service 包裝往上拋 → 頂層記一次完整堆疊+cause,回 500
 *   其他     → 成功,記 INFO,回 200
 *
 * 跑法:  mvn spring-boot:run    然後  curl -H 'X-Request-ID: demo-1' localhost:8080/users/42
 * 驗證:  mvn test
 */
@SpringBootApplication
public class App {
    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }
}
