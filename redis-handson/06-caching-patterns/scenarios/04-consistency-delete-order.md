# Scenario 04: 一致性 —— 先删缓存脏读复现 + 延迟双删

## 我想验证的问题

「先删缓存，再更 DB」的写策略，在并发读写下能不能留下「**缓存=旧、DB=新**」的脏数据？**延迟双删**能不能修复它？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.2，不要查）：
>
> - 「先删缓存→更 DB」并发一个读线程，我以为最终 cache 和 db 会 / 不会 不一致（选一个）。
> - 如果脏，脏在哪：cache=_____，db=_____。
> - 延迟双删的「延迟」要比什么时间长，才能盖住脏读窗口？_____
>
> 填完单独 commit 一次，再跑。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`
- 用 `db:k` 当「数据库源」，`cache:k` 当缓存；用 `sleep` 强制交错出问题窗口。

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
# A) 先删缓存策略,制造脏读
R flushall; R set db:k OLD; R set cache:k OLD
( R del cache:k >/dev/null; sleep 0.4; R set db:k NEW >/dev/null ) &                                   # 写:删缓存 ->(慢)更DB
( sleep 0.1; if [ "$(R exists cache:k)" = "0" ]; then v=$(R get db:k); sleep 0.5; R set cache:k "$v" >/dev/null; fi ) &  # 读:miss->读旧DB->回填
wait
echo "先删缓存: db=$(R get db:k) cache=$(R get cache:k)"
# B) 延迟双删:写线程更DB后,延迟再删一次缓存
R flushall; R set db:k OLD; R set cache:k OLD
( R del cache:k >/dev/null; sleep 0.4; R set db:k NEW >/dev/null; sleep 0.8; R del cache:k >/dev/null ) &
( sleep 0.1; if [ "$(R exists cache:k)" = "0" ]; then v=$(R get db:k); sleep 0.5; R set cache:k "$v" >/dev/null; fi ) &
wait
echo "延迟双删: db=$(R get db:k) cache_exists=$(R exists cache:k)"
```

## 实机告诉我（2026-06-01，Redis 7.4.9 实跑）

```
先删缓存: db=NEW cache=OLD          ← 脏!DB 新、缓存旧
延迟双删: db=NEW cache_exists=0      ← 旧缓存被二次删除,下次读回填为 NEW
```

交错时间线（先删缓存的脏读）：
```
t0  写: DEL cache:k          (缓存清空)
t1  读: EXISTS cache:k -> 0  (miss)
t2  读: GET db:k -> OLD       (此刻写还没更 DB)
t3  写: SET db:k NEW
t4  读: SET cache:k OLD       (把旧值回填!)  → 终态 cache=OLD, db=NEW
```

## ⚠️ 预期 vs 实机落差

- 我以为：删了缓存应该就安全了，下次读自然拿新值。
- 实际：删缓存和更 DB 之间有窗口，**读线程在这个窗口里 miss → 读到旧 DB → 把旧值回填**，于是缓存长期是旧的。延迟双删在「更 DB 后等一会儿再删一次」把这个被回填的旧值清掉。
- 我学到：(1) 脏读根因是「读的回填」和「写的删除」乱序，不是删没删的问题。(2) 这正是为什么 Cache-Aside 推荐**先更 DB 后删缓存**——把窗口缩到「删缓存那一下」，比「先删缓存」的整个更库期间都小。(3) 延迟双删的「延迟」必须 > 读线程「读 DB + 回填」耗时，否则第二次删还是删在回填之前，盖不住；这个延迟难精确估，所以生产更可靠的是 **binlog 订阅兜底删缓存**。

## 连到的面试卡

- `99-interview-cards/q-cache-consistency-update-order.md`
