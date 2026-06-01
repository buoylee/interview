# Scenario 01: MULTI/WATCH —— 乐观锁 abort + 运行时错误不回滚

## 我想验证的问题

(a) `WATCH k` 后、`EXEC` 前，另一个客户端把 k 改了，`EXEC` 会怎样？
(b) `MULTI` 队列里有一条命令运行时报错（对字符串 `INCR`），其余命令会不会被回滚？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1/§3.2，不要查）：
>
> - WATCH k 后被别人改了 k，EXEC 返回 _____，被 WATCH 的事务里的写 _____（生效/作废）。
> - MULTI 里 `SET a 1; INCR str(字符串); SET b 2`，EXEC 后 a=_____, b=_____（INCR 报错会不会回滚 a、b）？
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。注意 `MULTI`/`WATCH` 是**连接级**状态，要在**同一个连接**里跑 → 用「带 sleep 的管道喂一个 redis-cli」，sleep 期间用另一个连接改 key。

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
# (a) WATCH abort
R set k 0
( echo "WATCH k"; echo "GET k"; sleep 1; echo "MULTI"; echo "SET k fromA"; echo "EXEC"; echo "GET k" ) \
  | docker compose exec -T redis redis-cli &
sleep 0.4
R set k fromB          # B 在 A 的 WATCH 之后、EXEC 之前改 k
wait
echo "最终 k = $(R get k)"
# (b) 运行时错误不回滚
R set str hello
( echo "MULTI"; echo "SET a 1"; echo "INCR str"; echo "SET b 2"; echo "EXEC" ) \
  | docker compose exec -T redis redis-cli
echo "a=$(R get a)  b=$(R get b)"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
(a) A 的会话: WATCH→OK, GET k→0, MULTI→OK, SET k fromA→QUEUED, EXEC→(nil 空行), GET k→fromB
    最终 k = fromB                     ← A 的事务因 k 被改而整体作废,SET k fromA 没生效
(b) EXEC 返回: OK / "ERR value is not an integer" / OK
    a=1  b=2                            ← INCR str 报错,但 a、b 仍写入(不回滚)
```

观察到的关键事实：

- **WATCH abort**:B 在 WATCH 和 EXEC 之间改了 k，A 的 `EXEC` 返回 nil、整个事务作废，`SET k fromA` 没执行 → 最终 k 是 B 写的 `fromB`。
- **无回滚**:MULTI 队列里 `INCR str`（对字符串）运行时报错，但它**前后的 `SET a`、`SET b` 照常生效**——Redis 事务不回滚。

## ⚠️ 预期 vs 实机落差

- 我以为：`MULTI/EXEC` 是事务，里面有一条失败应该像 SQL 那样整体回滚。
- 实际:Redis 事务**没有回滚**。EXEC 期间不被打断(原子=不被插入别的命令),但某条运行时出错不影响其他命令——它保证的是「打包顺序执行」,不是「全成功或全失败」。WATCH 提供的是乐观锁(被改就作废),不是隔离级别。
- 我学到:(1) 别把 Redis 的 `MULTI` 当 RDBMS 事务用——没有 ACID 的原子回滚。(2) 入队时的**语法错误**会让整个 EXEC 拒绝,但**运行时错误**不会。(3) 要「检查通过才写、否则不写」这种逻辑,`MULTI` 做不到分支,得用 Lua(sc02)。

## 连到的面试卡

- `99-interview-cards/q-redis-transaction-vs-lua.md`
