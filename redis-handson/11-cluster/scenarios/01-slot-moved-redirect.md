# Scenario 01: 槽 / CRC16 / MOVED 重定向

## 我想验证的问题

cluster 里一个 key 怎么定位到节点？连到一个**不负责该 key 的节点**发命令会怎样？`redis-cli` 加不加 `-c` 有什么区别？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1/§3.2，不要查）：
>
> - `CLUSTER KEYSLOT foo` 返回什么（范围 0~16383）？怎么算的？_____
> - 在错节点上**非 `-c`** `SET foo` → 返回 _____。
> - 加 `-c` 后 `SET foo` → _____。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up-cluster && make cluster-init`，等 `cluster_state:ok`、`cluster_slots_assigned:16384`。
- `N1(){ docker compose exec -T redis-node-1 redis-cli "$@"; }`（非 -c）、`N1C(){ docker compose exec -T redis-node-1 redis-cli -c "$@"; }`（-c 自动重定向）

## 步骤

```bash
cd 00-lab && make up-cluster && make cluster-init
N1(){ docker compose exec -T redis-node-1 redis-cli "$@"; }
N1C(){ docker compose exec -T redis-node-1 redis-cli -c "$@"; }
# 等健康
until [ "$(N1 cluster info|grep -o 'cluster_state:[a-z]*'|tr -d '\r')" = "cluster_state:ok" ]; do sleep 1; done
N1 cluster info | grep -E 'cluster_state|cluster_slots_assigned'
echo "KEYSLOT foo=$(N1 cluster keyslot foo)  bar=$(N1 cluster keyslot bar)"
echo "非 -c SET foo: $(N1 set foo 1)"          # 错节点 → MOVED
echo "-c   SET foo: $(N1C set foo 1)"          # 自动重定向 → OK
echo "-c   GET foo: $(N1C get foo)"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑，3 主 3 从）

```
cluster_state:ok
cluster_slots_assigned:16384
KEYSLOT foo=12182   bar=5061
非 -c SET foo: MOVED 12182 192.168.147.6:6379    ← foo 的槽 12182 归另一节点
-c   SET foo: OK                                 ← redis-cli -c 跟随重定向
-c   GET foo: 1
```

观察到的关键事实：

- key 通过 `CRC16(key) % 16384` 映射到槽：`foo`→12182、`bar`→5061（不同 key 落不同槽 → 分散到不同节点）。
- 在不负责 `foo` 的节点上**非 `-c`** 发 `SET foo`，返回 **`MOVED 12182 192.168.147.6:6379`**——告诉你正确的节点。
- `-c`（cluster 模式）会**自动跟随 MOVED 重连**正确节点，`SET`/`GET` 直接成功。

## ⚠️ 预期 vs 实机落差

- 我以为：连上任意一个 cluster 节点就能读写任意 key。
- 实际:每个节点只负责一部分槽,key 不归它管就回 **MOVED**(重定向错误,不是真错误)。**客户端**(`-c` 或 cluster-aware 库)负责维护「槽→节点」路由表、跟随 MOVED;裸 `redis-cli`(无 -c)只把 MOVED 当错误打印出来。
- 我学到:(1) 定位 = `CRC16(key)%16384` → 槽 → 负责该槽的 master。(2) MOVED 是「永久换家」:好的客户端收到后会刷新整张路由表,之后直连正确节点(不是每次都先撞一下)。(3) 生产用支持 cluster 的客户端(Lettuce/JedisCluster/redis-py-cluster),它们自动管路由,你代码无感。

## 连到的面试卡

- `99-interview-cards/q-redis-cluster.md`
