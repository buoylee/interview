# Redis 事务(MULTI)有回滚吗？为什么很多场景用 Lua？

## 一句话回答

`MULTI/EXEC` 把命令**打包顺序执行、不被打断**,但**没有回滚**(运行时错误不回滚已执行命令);`WATCH` 加乐观锁 CAS。真正灵活的原子逻辑(检查-再-改、防超卖)用 **Lua**(整脚本原子 + 能在执行中读值分支)。`pipeline` 只省 RTT、**不是事务**。

## MULTI vs Lua vs pipeline

| | 原子(不被打断) | 回滚 | 执行中能读值分支 | 用途 |
|---|---|---|---|---|
| MULTI/EXEC | ✅ | ❌ 无回滚 | ❌(只能排队) | 一组命令打包 |
| WATCH + MULTI | ✅ | ❌ | ❌ | 乐观锁 CAS |
| Lua(EVAL) | ✅ | ❌(但可自己控制) | ✅ | 检查-修改原子逻辑 |
| pipeline | ❌ | ❌ | ❌ | 省 RTT 提吞吐 |

## 实测证据

- MULTI 无回滚:队列里 `INCR 字符串` 报错,前后 `SET a`、`SET b` 仍生效(a=1,b=2)。WATCH 被改 → EXEC 作废。[sc01](../08-transactions-scripting/scenarios/01-multi-watch-no-rollback.md)
- 非原子 GET-then-DECR 20 抢 5 → stock=**-15 超卖**;Lua 原子 check-and-decr → stock=**0 不超卖**。[sc02](../08-transactions-scripting/scenarios/02-lua-atomic-vs-race.md)

## 易追问的延伸

- **为什么 Redis 事务不回滚?** 设计哲学:运行时错误多是编程 bug(用错类型),回滚增加复杂度;入队时的语法错误才整体拒绝。
- **WATCH 热点 key 会怎样?** 频繁 abort、空转重试(重试风暴),改用 Lua 或分布式锁(07 章)。
- **Lua 脚本要注意什么?** 别写大遍历/重循环(占单线程卡全场,01 章);保持确定性。
- **EVAL vs FUNCTION(7.0)?** FUNCTION 注册命名函数库常驻(FCALL),EVAL 每次传脚本靠 SHA 缓存。

## 证据链接

- 章节原理:[08-transactions-scripting](../08-transactions-scripting/README.md)
- 实测:[sc01 MULTI/WATCH](../08-transactions-scripting/scenarios/01-multi-watch-no-rollback.md)、[sc02 Lua 原子](../08-transactions-scripting/scenarios/02-lua-atomic-vs-race.md)
- 相关:缓存击穿互斥(06 sc02)、限流(13 章)同样用 Lua
