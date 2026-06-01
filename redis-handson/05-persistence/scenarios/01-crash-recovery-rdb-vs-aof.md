# Scenario 01: 崩溃恢复 —— RDB-only 丢数据 vs AOF 不丢 + multi-part AOF 结构

## 我想验证的问题

写入一批数据后 `kill -9`（模拟崩溃），重启能恢复多少？分两种配置:RDB-only（无快照）vs AOF（everysec）。7.x 的 AOF 文件到底长什么样？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1/§3.4，不要查）：
>
> - RDB-only（`appendonly no`、`save ''`）写 100 个 key 后 `kill -9`、重启 → dbsize=_____。
> - AOF（`appendonly yes everysec`）同样操作 → dbsize=_____。
> - 7.x 的 AOF 目录里有哪几个文件？base 是什么格式？_____
>
> 填完单独 commit 一次。

## 环境

- 用**独立临时容器 + 命名卷**做崩溃测试（不污染 lab 的 redis）。
- `kill -9` = `docker kill -s SIGKILL`（不给 Redis 优雅退出/落盘的机会）。

## 步骤

```bash
cleanup(){ docker rm -f rtest >/dev/null 2>&1; docker volume rm rtv >/dev/null 2>&1; }
# --- RDB-only ---
cleanup; docker volume create rtv >/dev/null
docker run -d --name rtest -v rtv:/data redis:7.4 redis-server --appendonly no --save ''; sleep 1
for i in $(seq 1 100); do docker exec rtest redis-cli set k:$i v$i >/dev/null; done
docker exec rtest redis-cli dbsize          # 100
docker kill -s SIGKILL rtest; docker rm rtest
docker run -d --name rtest -v rtv:/data redis:7.4 redis-server --appendonly no --save ''; sleep 1
docker exec rtest redis-cli dbsize          # 重启后?
# --- AOF everysec ---
cleanup; docker volume create rtv >/dev/null
docker run -d --name rtest -v rtv:/data redis:7.4 redis-server --appendonly yes --appendfsync everysec --save ''; sleep 1
for i in $(seq 1 100); do docker exec rtest redis-cli set k:$i v$i >/dev/null; done
sleep 1.2                                   # 等 everysec 刷盘
docker kill -s SIGKILL rtest; docker rm rtest
docker run -d --name rtest -v rtv:/data redis:7.4 redis-server --appendonly yes --save ''; sleep 1
docker exec rtest redis-cli dbsize          # 重启后?
docker exec rtest ls /data/appendonlydir    # 看 AOF 文件结构
cleanup
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
RDB-only:  写完 dbsize=100  → kill -9 → 重启 dbsize=0     ← 无快照,全丢
AOF:       写完 dbsize=100  → kill -9 → 重启 dbsize=100   ← AOF 重放,全在
AOF 目录:  appendonly.aof.1.base.rdb   appendonly.aof.1.incr.aof   appendonly.aof.manifest
```

观察到的关键事实：

- **RDB-only 崩溃 → 数据全丢**：没到 `save` 触发点、又没 AOF，`kill -9` 后重启加载的是空/旧 RDB，100 个 key 归零。
- **AOF everysec → 数据全在**：写命令进了 AOF（everysec 刷盘窗口内已落盘），重启重放恢复 100 个 key。
- **7.x 是 multi-part AOF**:`appendonlydir/` 下 `*.base.rdb`(**base 用 RDB 格式**——这就是「混合持久化」)+ `*.incr.aof`(增量命令)+ `manifest`(清单)。

## ⚠️ 预期 vs 实机落差

- 我以为：Redis 默认就会持久化,崩了也能恢复;AOF 是一个单独的 `appendonly.aof` 文件。
- 实际:**RDB-only 在快照之间崩溃会丢光这段数据**;要不丢得靠 AOF。而且 7.x 的 AOF 已经是**一组文件**(multi-part),base 直接用 RDB 格式——「混合持久化」不是一个开关而是默认结构。
- 我学到:(1) 「会不会丢数据」取决于持久化配置:RDB-only 丢快照间、AOF everysec 丢 ~1s。(2) RDB+AOF 同开时重启**优先用 AOF**(丢得最少)。(3) `kill -9` 才是真崩溃测试;`docker stop`(SIGTERM)会让 Redis 优雅落盘,测不出丢数据。

## 连到的面试卡

- `99-interview-cards/q-redis-persistence.md`
