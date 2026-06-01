# Redis Hands-on 第 07 章 分布式锁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans 逐 task 执行。

**Goal:** 写出 `07-distributed-locks` 的 7 段 README + 3 个**已实测**可跑 scenario(CAS 安全释放/看门狗续期/主从切换丢锁)+ 2 张面试卡,把分布式锁从「知道 Redisson/RedLock 名词」做到「亲手复现误删、续期、主从丢锁」。

**Architecture:** 单机 Redis 跑 sc01/02(SET NX PX + Lua CAS + bash 后台模拟看门狗);sentinel profile 跑 sc03(故障转移 + 网络分区复现丢锁)。Java/Redisson + redis-py 为 README 对照镜像。

**Tech Stack:** Redis 7.4、redis-cli、Lua、bash 后台、sentinel profile、`docker network disconnect`。

参考 spec §07。复用旧笔记:`redis/redisson-rlock.md`、`redis/redlock.md`、`redis/分布式锁-redlock.md`、`redis/事务-lua.md`。范式:`02-data-structures/`、`06-caching-patterns/`。

---

## File Structure

```
redis-handson/07-distributed-locks/
├── README.md
└── scenarios/
    ├── 01-setnx-lua-safe-release.md       获取/释放 + 误删复现 + Lua CAS 修复
    ├── 02-watchdog-renewal.md             看门狗续期:超时续期 vs 停续期过期
    └── 03-failover-lock-loss.md           主从切换丢锁:pause 没丢 vs 真断网丢失+双重持有
redis-handson/99-interview-cards/
├── q-redis-distributed-lock-correctness.md
└── q-redlock-controversy.md
```

## Cross-cutting conventions
- 单机 scenario:`make up`;`R(){ docker compose exec -T redis redis-cli "$@"; }`。
- sc03 用 sentinel profile;容器名是 compose 自动名(用 `docker compose pause/exec <service>`,不要 `docker pause <name>`)。
- 锁约定:`SET key token NX PX ttl` + Lua CAS 释放(`get==token then del`)。
- 每 scenario 一次 commit;预期空格留学习者。

---

### Task 1: 写 07-distributed-locks/README.md（7 段）

要点(写作展开):
1. **核心问题**:多进程/多机互斥;怎么加锁解锁才安全(不误删、不死锁、不丢锁)。
2. **直觉**:锁 = 一个「谁先 SET 成功谁拥有」的 key;难点全在异常路径——持有者崩了(要自动过期)、过期了又被别人占(解锁要校验归属)、Redis 自己挂了(主从切换锁可能蒸发)。
3. **原理深入**:
   - 正确加锁:`SET key <uniq-token> NX PX <ttl>`(NX 互斥、PX 防死锁、token 标识归属)。**为什么解锁要 Lua CAS**:先 GET 比 token 再 DEL,两步必须原子,否则「判断后、删除前」锁过期被别人拿走→误删别人的锁(sc01 复现)。
   - **看门狗**:业务没跑完锁就过期怎么办?Redisson 后台线程每 `ttl/3` 续期(`PEXPIRE`),续到业务结束或客户端崩溃(sc02 模拟)。
   - **主从切换丢锁**:Redis 复制是异步的,master 确认加锁后若在复制前宕机,slave 升主后没这把锁→两个客户端同时"持有"(sc03 复现)。
   - **RedLock**:向 N 个独立 master 各加锁,过半成功才算获得。**Martin Kleppmann 的质疑**:GC 停顿/时钟漂移下 RedLock 也不保证正确,真正的正确性要靠 **fencing token**(单调递增,被保护资源校验 token 拒绝旧持有者);antirez 的回应。
4. **日常开发**:别手撸,用 Redisson `RLock`(自带 token+看门狗+可重入);锁粒度要细;一定设兜底过期;关键资源加 fencing。
5. **调优实战**:锁竞争激烈→看是不是锁粒度太粗;锁经常超时→看门狗或调大 ttl;排查"锁莫名丢失"先怀疑主从切换。
6. **面试高频**:为什么 Lua 释放、SET NX 为什么要 PX、看门狗原理、RedLock 争议与 fencing token、可重入怎么实现(hash 存 token+计数)。
7. **一句话总结**:`SET NX PX <token>` 加锁 + Lua CAS 释放 + 看门狗续期是单实例正确姿势;跨主从有丢锁窗口,强正确性靠 fencing token,不是靠锁本身。

- README 末 **对照镜像**:Redisson `RLock`(tryLock/lease/看门狗/可重入)、redis-py 手写(`set nx px` + Lua release）。
- 末尾 Scenarios 列表。
- **Commit** `redis-handson: 07-distributed-locks README(7段+CAS+看门狗+RedLock争议+fencing)`

---

### Task 2: Scenario 01 — SET NX PX + Lua CAS 安全释放（含误删复现）

**已实测**步骤:

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
# 加锁互斥
echo "A 抢锁: $(R set lock:x tokenA nx px 10000)"   # OK
echo "B 抢同一把: $(R set lock:x tokenB nx px 10000)" # nil(空)
# 误删复现:B 无脑 DEL(不校验归属)删掉了 A 的锁
echo "B 无脑 DEL: $(R del lock:x)"                    # 1  <- 删了别人的锁!
# Lua CAS 安全释放:token 不匹配不删
R set lock:y tokenA nx px 10000 >/dev/null
CAS='if redis.call("get",KEYS[1])==ARGV[1] then return redis.call("del",KEYS[1]) else return 0 end'
echo "错 token CAS 释放: $(R eval "$CAS" 1 lock:y tokenB)"  # 0 不删
echo "对 token CAS 释放: $(R eval "$CAS" 1 lock:y tokenA)"  # 1 删掉
```

实机参考:A=OK、B=nil、无脑 DEL=1(危险)、错 token=0、对 token=1。
落差点:不带 token 的 DEL 会删掉「自己过期后别人新拿到」的锁;判断+删除必须 Lua 原子(否则中间锁过期被抢走仍误删)。

- **Commit** `redis-handson: scenario 07-01 SET NX PX + Lua CAS 安全释放(误删复现)`

---

### Task 3: Scenario 02 — 看门狗续期

**已实测**步骤:

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R set lock:wd holder px 2000 >/dev/null
echo "初始 pttl=$(R pttl lock:wd)"
# 后台看门狗:每 0.6s PEXPIRE 续回 2000,续 3 次(覆盖 ~1.8s)
( for n in 1 2 3; do sleep 0.6; docker compose exec -T redis redis-cli pexpire lock:wd 2000 >/dev/null; done ) &
sleep 2.2; echo "2.2s 后(无续期本应过期)exists=$(R exists lock:wd) pttl=$(R pttl lock:wd)"
wait
sleep 2.3; echo "停续期 2.3s 后 exists=$(R exists lock:wd)"
```

实机参考:初始 pttl≈1922;2.2s 后 exists=1(续期续命);停续期 2.3s 后 exists=0(过期)。
落差点:看门狗让锁随「持有者存活」续命,而非到固定 ttl 就死;持有者崩溃→续期停止→锁自动释放(兜底),这就是 ttl 不能省的原因。

- **Commit** `redis-handson: scenario 07-02 看门狗续期`

---

### Task 4: Scenario 03 — 主从切换丢锁（pause 没丢 vs 真断网丢失）

**已实测**步骤(sentinel profile):

```bash
cd 00-lab && make up-sentinel   # 等 2 slaves online
# 实验 A:pause 两 replica → master 加锁 → 杀 master → unpause → 故障转移 → 查新主
#   结果:锁"幸存"(tokenA 在新主)。因为 pause 只冻进程,复制字节已进内核 TCP 缓冲,unpause 后补传。
# 实验 B:docker network disconnect 两 replica(真断网)→ master 加锁 → 杀 master → reconnect → 故障转移
#   结果:新主 lock:critical=[](丢了)→ 另一客户端 SET NX=OK(双重持有)。
# 检测故障转移完成:轮询 sentinel get-master-addr-by-name 直到地址"变化"(不是非空,旧主未判定下线时返回旧址)
```

（完整脚本见本 plan 末「sc03 脚本」附录，已逐行实跑通过。）

实机参考:实验 A 新主仍有 tokenA;实验 B 新主为空 + 重抢 OK(双重持有),故障转移 ~18–29s。
落差点(本章最有料):**用 pause 模拟丢锁丢不掉**——TCP 缓冲让复制字节在 unpause 后补达;**只有真网络分区(写入前字节根本没发出)才丢锁**。这恰好说明异步复制的丢锁窗口「窄但真实」,也是 RedLock + fencing token 存在的理由。

- **Commit** `redis-handson: scenario 07-03 主从切换丢锁(pause 没丢/真断网丢失+双重持有)`

---

### Task 5: 面试卡 — 分布式锁正确姿势

`q-redis-distributed-lock-correctness.md`:一句话(`SET NX PX <token>` + Lua CAS 释放 + 看门狗)+ 三个异常路径(死锁→PX、误删→token+Lua、超时→看门狗)+ 可重入(hash 存 token+计数)+ 链回 sc01/02 + 易追问。
- **Commit** `redis-handson: 面试卡 分布式锁正确姿势`

### Task 6: 面试卡 — RedLock 争议

`q-redlock-controversy.md`:一句话(RedLock=N 个独立 master 过半;Kleppmann 质疑 GC/时钟下不安全;正确性靠 fencing token)+ 单实例丢锁窗口(链回 sc03)+ fencing token 机制 + 何时该用/不该用 + 易追问。
- **Commit** `redis-handson: 面试卡 RedLock 争议与 fencing token`

---

## sc03 脚本（已实跑）

```bash
cd 00-lab
NET=$(docker compose ps redis --format '{{.Networks}}' | head -1)
make up-sentinel
M(){ docker compose exec -T redis-m redis-cli "$@"; }
SN(){ docker compose exec -T redis-sn-1 redis-cli -p 26379 "$@"; }
until [ "$(M info replication 2>/dev/null | grep -c 'state=online')" = "2" ]; do sleep 1; done
ORIG=$(SN sentinel get-master-addr-by-name mymaster | head -1 | tr -d '\r')
R1=$(docker compose ps redis-r1 --format '{{.Name}}'); R2=$(docker compose ps redis-r2 --format '{{.Name}}')
# --- 实验 B:真断网 ---
docker network disconnect $NET $R1; docker network disconnect $NET $R2
M set lock:critical tokenA px 60000; M get lock:critical
docker compose stop redis-m
docker network connect $NET $R1; docker network connect $NET $R2
NEWIP="$ORIG"; i=0
until [ "$NEWIP" != "$ORIG" ] || [ $i -ge 45 ]; do NEWIP=$(SN sentinel get-master-addr-by-name mymaster 2>/dev/null | head -1 | tr -d '\r'); i=$((i+1)); sleep 1; done
Q(){ docker compose exec -T redis-sn-1 redis-cli -h "$NEWIP" -t 2 "$@" 2>/dev/null | tr -d '\r'; }
echo "新主 lock:critical=[$(Q get lock:critical)]"      # 空=丢
echo "重抢=[$(Q set lock:critical tokenB nx px 60000)]"  # OK=双重持有
make down-sentinel; docker compose up -d redis
```
> 实验 A 把 `network disconnect/connect` 换成 `docker compose pause/unpause redis-r1 redis-r2` 即可(结果:锁幸存)。

## Self-Review
- 覆盖 spec §07(SET NX+Lua / 看门狗 / RedLock 争议 / 主从丢锁 / redis-py 对照)。✅
- 3 个 scenario 全部已实跑(sc01 CAS、sc02 看门狗、sc03 pause vs 断网)。✅
- 命名一致:`lock:x/y/wd/critical`、`tokenA/B`、CAS 脚本。✅

**下一步**:执行(README→sc01-03→2 卡),sc03 跑完务必 `make down-sentinel` + 起回单机。
