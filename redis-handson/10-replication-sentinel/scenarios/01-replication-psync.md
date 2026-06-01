# Scenario 01: 主从复制 + 只读 + psync 全量/部分

## 我想验证的问题

从节点能不能复制主的数据、能不能写？从节点首次连接走全量还是部分复制？短暂断线重连呢？怎么从 `INFO` 看出来？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1，不要查）：
>
> - 主写 `foo=bar`，从能读到吗？从能写吗（返回什么）？
> - 从**首次连接**主，走全量还是部分复制？`INFO stats` 哪个计数 +1？_____
> - 从**短暂断线重连**（连接被 kill 但很快重连），走全量还是部分？哪个计数 +1？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up-sentinel`（1 主 redis-m + 2 从 redis-r1/r2）。等 2 从 online。
- `M(){ docker compose exec -T redis-m redis-cli "$@"; }`、`R1(){ docker compose exec -T redis-r1 redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up-sentinel
M(){ docker compose exec -T redis-m redis-cli "$@"; }
R1(){ docker compose exec -T redis-r1 redis-cli "$@"; }
until [ "$(M info replication 2>/dev/null|grep -c state=online)" = "2" ]; do sleep 1; done
# 复制 + 只读
M set foo bar; sleep 0.3
echo "replica 读 foo = $(R1 get foo)"
echo "replica 写: $(R1 set x 1)"
echo "master role=$(M role|head -1)  replica role=$(R1 role|head -1)"
# psync 计数
echo "首连后: sync_full=$(M info stats|grep -o 'sync_full:[0-9]*')  sync_partial_ok=$(M info stats|grep -o 'sync_partial_ok:[0-9]*')"
# 制造短暂断线:kill 复制连接 → 从重连应走部分复制
M client kill type replica; sleep 3
echo "断连重连后: sync_full=$(M info stats|grep -o 'sync_full:[0-9]*')  sync_partial_ok=$(M info stats|grep -o 'sync_partial_ok:[0-9]*')"
make down-sentinel; docker compose up -d redis
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
replica 读 foo = bar                                ← 复制成功
replica 写 x:  READONLY You can't write against a read only replica.
master role=master  replica role=slave
首连后:     sync_full=2   sync_partial_ok=0         ← 2 个从首次连接,各走全量
断连重连后: sync_full=2   sync_partial_ok=2         ← 短断重连,走部分复制(没再全量)
```

观察到的关键事实：

- 主写从读、**从只读**（写报 `READONLY`），role 一主一从。
- **首次连接 = 全量复制**：2 个从首连，`sync_full=2`（主 BGSAVE 出 RDB 发给从）。
- **短暂断线重连 = 部分复制**：`CLIENT KILL type replica` 断开复制连接后从重连，`sync_partial_ok` 从 0 → 2（从 repl-backlog 补缺失命令，**没有再全量**），`sync_full` 不变。

## ⚠️ 预期 vs 实机落差

- 我以为：从掉线重连都要重新全量同步一遍。
- 实际:只要断得不久、缺的数据还在**复制积压缓冲区(repl-backlog)**里,就走**部分复制**(CONTINUE)只补差量——`sync_partial_ok` 涨而 `sync_full` 不涨。只有断太久、backlog 装不下,才退化为全量。
- 我学到:(1) psync 两种:首连/backlog 溢出 → 全量(FULLRESYNC + RDB);短断 → 部分(CONTINUE,补 backlog)。(2) 频繁全量很伤(BGSAVE + 传 RDB),网络抖动多就调大 `repl-backlog-size`。(3) 从默认只读;读写分离时要意识到主从延迟 → 从可能读到旧值(最终一致)。

## 连到的面试卡

- `99-interview-cards/q-redis-replication-sentinel.md`
