package com.example;

import java.util.Map;

import org.springframework.stereotype.Service;

/** 04:資料/服務層只「包裝 + 往上拋」,不在這裡記 log。 */
@Service
public class UserService {

    public Map<String, Object> fetch(long id) {
        if (id == 99) {
            try {
                // 模擬下游/DB 故障
                throw new RuntimeException("connection reset by peer");
            } catch (RuntimeException e) {
                // 04:包裝成業務異常,e 當 cause 保留 chain,但「不在這裡記」
                throw new RepositoryException("load user failed, id=" + id, e);
            }
        }
        if (id == 13) {
            throw new UserNotFoundException(id); // 可預期業務狀況
        }
        return Map.of("id", id, "name", "user" + id);
    }
}
