# Scenario 02: hash tag —— multi-key 跨槽 CROSSSLOT 与同槽

## 我想验证的问题

cluster 里对多个 key 做 `MSET`（multi-key），如果它们落在不同槽会怎样？怎么强制把几个 key 放到同一个槽，让 multi-key 命令能用？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3，不要查）：
>
> - `MSET a 1 b 2 c 3`（a/b/c 多半不同槽）→ 返回 _____。
> - `{u}:a` 和 `{u}:b` 的 KEYSLOT 一样吗？为什么？_____
> - `MSET {u}:a 1 {u}:b 2` → _____。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up-cluster && make cluster-init`（等 `cluster_state:ok`）。
- `N1C(){ docker compose exec -T redis-node-1 redis-cli -c "$@"; }`、`N1(){ docker compose exec -T redis-node-1 redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up-cluster && make cluster-init
N1(){ docker compose exec -T redis-node-1 redis-cli "$@"; }
N1C(){ docker compose exec -T redis-node-1 redis-cli -c "$@"; }
until [ "$(N1 cluster info|grep -o 'cluster_state:[a-z]*'|tr -d '\r')" = "cluster_state:ok" ]; do sleep 1; done
echo "MSET a b c(不同槽): $(N1C mset a 1 b 2 c 3)"
echo "KEYSLOT {u}:a=$(N1 cluster keyslot '{u}:a')  {u}:b=$(N1 cluster keyslot '{u}:b')"
echo "MSET {u}:a {u}:b(hash tag 同槽): $(N1C mset '{u}:a' 1 '{u}:b' 2)"
echo "MGET {u}:a {u}:b: $(N1C mget '{u}:a' '{u}:b')"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
MSET a 1 b 2 c 3:  CROSSSLOT Keys in request don't hash to the same slot
KEYSLOT {u}:a=11826   {u}:b=11826         ← 都用 {u} 算,落同一槽
MSET {u}:a 1 {u}:b 2:  OK
MGET {u}:a {u}:b:  1 2
```

观察到的关键事实：

- `MSET a 1 b 2 c 3`：a/b/c 各自 `CRC16%16384` 落不同槽 → multi-key 命令直接报 **`CROSSSLOT`**（cluster 不允许跨槽的 multi-key）。
- 带 hash tag `{u}` 时，**只对 `{}` 内的 `u` 算槽** → `{u}:a` 和 `{u}:b` 都落槽 11826（同槽）。
- 同槽后 `MSET`/`MGET` 正常工作。

## ⚠️ 预期 vs 实机落差

- 我以为：cluster 里 `MSET`/事务/Lua 跟单机一样随便用多个 key。
- 实际:cluster 下 multi-key 命令(含 `MSET`、`MGET`、`SINTERSTORE`、MULTI 事务、多 key Lua)**要求所有 key 在同一槽**,否则 `CROSSSLOT`。要让它们同槽,得用 **hash tag `{}`** 把算槽的部分固定成同一串。
- 我学到:(1) 设计 cluster key 时,把「需要一起原子操作」的 key 用相同 hash tag(如 `{userid}`):`cart:{1001}`、`order:{1001}` 落同槽,可一起 MSET/事务/Lua。(2) **别滥用**——同 tag 的 key 全挤一个槽/节点,会数据倾斜、制造热点(12 章)。(3) 这是 cluster 相比单机的一大约束,迁移到 cluster 前要审查所有 multi-key 用法。

## 连到的面试卡

- `99-interview-cards/q-redis-cluster.md`
