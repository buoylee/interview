# Redis Hands-on 第 06 章 缓存模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:executing-plans 逐 task 执行。步骤用 `- [ ]`。

**Goal:** 写出 `06-caching-patterns` 的 7 段 README + 4 个可实跑 scenario(穿透/击穿/雪崩/一致性)+ 面试卡,把使用者「会背名词、不会落地」的缓存真空区补成「亲手复现过」。

**Architecture:** lab 是 cli-only 单机 Redis(无独立 DB),用 **Redis 键模拟「数据库源」+ 后台并发 redis-cli + 注入 sleep 强制交错 + Lua 原子** 来复现并发问题。Java/Redisson + redis-py 只在 README 作「对照镜像」代码片段(不在 lab 跑)。

**Tech Stack:** Redis 7.4、redis-cli、Lua(EVAL)、bash 后台并发、`make up`。

参考 spec:`docs/superpowers/specs/2026-06-01-redis-handson-design.md` §06。
复用旧笔记:`redis/缓存.md`、`redis/缓存穿透.md`。
范式样板:`redis-handson/02-data-structures/`(7 段 + scenario 纪律 + 卡片)。

---

## File Structure

```
redis-handson/06-caching-patterns/
├── README.md                       ← 7 段(Task 1)
└── scenarios/
    ├── 01-penetration-bloom.md           穿透:bitmap 布隆挡不存在 key(Task 2)
    ├── 02-breakdown-mutex-rebuild.md      击穿:SET NX 互斥重建 vs 无锁惊群(Task 3)
    ├── 03-avalanche-ttl-jitter.md         雪崩:TTL 同时过期 vs 随机抖动(Task 4)
    └── 04-consistency-delete-order.md     一致性:先删缓存脏读复现 + 延迟双删(Task 5)
redis-handson/99-interview-cards/
├── q-cache-penetration-breakdown-avalanche.md   (Task 6)
└── q-cache-consistency-update-order.md           (Task 7)
```

## Cross-cutting conventions

- 所有 scenario 开头:`cd 00-lab && make up`;`R(){ docker compose exec -T redis redis-cli "$@"; }`。
- 「数据库源」建模为 redis 键 `db:<k>`,缓存键 `cache:<k>`;「慢 DB」用 `sleep` 模拟。
- scenario 纪律同 02 章:`预期` 空格留给学习者;`实机告诉我` 贴真跑输出;`⚠️落差` 写真实发现。
- 每 scenario 一次 commit(02 章 sc01 已示范两段提交,后续单提交)。
- commit 前缀 `redis-handson:`。

---

### Task 1: 写 06-caching-patterns/README.md(7 段)

**Files:** Modify `redis-handson/06-caching-patterns/README.md`(替换 stub)

- [ ] **Step 1: 写 7 段**,要点如下(写作时展开成完整段落):

  1. **核心问题**:缓存怎么读写(Cache-Aside/Read-Through/Write-Through/Write-Back)、并发下怎么保证缓存与 DB 一致、三大失效场景(穿透/击穿/雪崩)怎么防。
  2. **直觉理解**:缓存是「DB 的快照副本」,副本和正本之间任何「读旧→写回」或「更新顺序」的窗口都会留下不一致;三大失效是「请求穿过缓存砸到 DB」的三种姿势(查不存在的 / 单个热 key 失效瞬间 / 大批 key 同时失效)。
  3. **原理深入**:
     - 四种读写模式对比表(谁负责回填、谁负责写 DB、一致性/性能权衡)。
     - **一致性核心**:为什么「先更 DB 再删缓存」(Cache-Aside 标准)优于「先删缓存再更 DB」;两者各自的脏读窗口;**延迟双删**怎么补「先删缓存」的窗口;`binlog 订阅删缓存`(Canal)作为兜底。配时序图(文字版)。
     - **三大失效**:穿透(查 DB 也没有 → 布隆 / 缓存空值)、击穿(热 key 失效瞬间惊群 → 互斥重建 / 逻辑过期 / 永不过期)、雪崩(大批同时失效 → TTL 随机抖动 / 多级缓存 / 熔断)。
  4. **日常开发应用**:默认用 Cache-Aside「读:miss 回填;写:先更 DB 后删缓存」;TTL 一律加随机抖动;高频热 key 用互斥或逻辑过期重建;查询接口前置布隆。
  5. **调优实战**:缓存命中率怎么看(`INFO stats` 的 `keyspace_hits/misses`);热 key 怎么发现(12 章 `--hotkeys`);大量空值缓存的内存控制(短 TTL)。
  6. **面试高频考点**:先删 vs 先写顺序、延迟双删为什么是「延迟」、布隆假阳性的业务影响、击穿三解法对比、雪崩为什么加随机数。
  7. **一句话总结**:缓存默认 Cache-Aside + 先更库后删缓存 + TTL 抖动 + 布隆挡穿透 + 互斥/逻辑过期挡击穿;一致性只能做到「最终一致 + 缩小窗口」,要强一致就别用缓存。

- [ ] **Step 2: README 末尾「对照镜像」小节**,给三段参考代码(不在 lab 跑,标注「reference」):
  - Java/Redisson:`RBloomFilter`(穿透)、`RLock` 保护重建(击穿)。
  - redis-py:`set(nx=True, ex=...)` 互斥重建 + `SETBIT/GETBIT` 布隆。
  - 说明:scenario 用 cli/Lua 跑原理,生产落地用这些客户端封装。

- [ ] **Step 3: README 末尾 Scenarios 列表**(4 条链接)。

- [ ] **Step 4: Commit** `redis-handson: 06-caching-patterns README(7段+四模式+一致性+对照镜像)`

---

### Task 2: Scenario 01 — 穿透:bitmap 布隆挡不存在 key

**Files:** Create `redis-handson/06-caching-patterns/scenarios/01-penetration-bloom.md`

- [ ] **Step 1: 写 scenario**。问题:用 bitmap 自实现布隆(k=2 个 hash),验证「**无假阴性**(存在的一定放行)」+「**有假阳性**(灌满后不存在的可能误放)」。预期段留空格给学习者。可跑步骤(**已实测**):

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
# A) 直觉:8192 位 bitmap "bf",注册 1001,1002,挡 9999
R eval "for i,v in ipairs(ARGV) do local h1=redis.sha1hex(v) local a=tonumber(string.sub(h1,1,8),16)%8192 local b=tonumber(string.sub(h1,9,16),16)%8192 redis.call('setbit','bf',a,1) redis.call('setbit','bf',b,1) end return 'ok'" 0 1001 1002 >/dev/null
CHECK='local h1=redis.sha1hex(ARGV[1]) local a=tonumber(string.sub(h1,1,8),16)%8192 local b=tonumber(string.sub(h1,9,16),16)%8192 if redis.call("getbit","bf",a)==1 and redis.call("getbit","bf",b)==1 then return 1 else return 0 end'
echo "1001->$(R eval "$CHECK" 0 1001)  1002->$(R eval "$CHECK" 0 1002)  9999->$(R eval "$CHECK" 0 9999)"  # 期望 1 1 0
# B) 假阳性演示:故意用小 bitmap(1024 位)灌入 300 个 id,逼出假阳性
R del bf2 >/dev/null
R eval "for i=1,300 do local h1=redis.sha1hex(tostring(i)) local a=tonumber(string.sub(h1,1,8),16)%1024 local b=tonumber(string.sub(h1,9,16),16)%1024 redis.call('setbit','bf2',a,1) redis.call('setbit','bf2',b,1) end return 'ok'" 0 >/dev/null
CHECK2='local h1=redis.sha1hex(ARGV[1]) local a=tonumber(string.sub(h1,1,8),16)%1024 local b=tonumber(string.sub(h1,9,16),16)%1024 if redis.call("getbit","bf2",a)==1 and redis.call("getbit","bf2",b)==1 then return 1 else return 0 end'
fn=0; for i in $(seq 1 300); do [ "$(R eval "$CHECK2" 0 $i)" = "0" ] && fn=$((fn+1)); done; echo "假阴性(必须=0): $fn"
fp=0; for i in $(seq 10001 10300); do [ "$(R eval "$CHECK2" 0 $i)" = "1" ] && fp=$((fp+1)); done; echo "假阳性: $fp / 300  (bitcount=$(R bitcount bf2)/1024)"
```

- [ ] **Step 2: 跑并填实机**(实测:1001/1002→1、9999→0;假阴性=0;假阳性≈71/300,bitcount≈466/1024)。落差点:布隆「**说不存在就一定不存在**(零假阴性,所以能安全挡穿透),**说存在可能是假阳性**」;假阳性的 key 漏到 DB 但绝不错杀真实 key;假阳性率随 bitmap 装填率上升——容量要按预估元素数留够。
- [ ] **Step 3: Commit** `redis-handson: scenario 06-01 穿透 bitmap 布隆`

---

### Task 3: Scenario 02 — 击穿:SET NX 互斥重建 vs 无锁惊群

**Files:** Create `redis-handson/06-caching-patterns/scenarios/02-breakdown-mutex-rebuild.md`

- [ ] **Step 1: 写 scenario**。问题:热 key 失效瞬间 N 个并发请求,无锁时几个回源重建?加 `SET NX` 互斥后几个?用「重建计数器」`rebuild:cnt` 度量。可跑步骤(后台并发 + 模拟慢重建):

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
# --- 无锁:10 个并发,缓存 miss 就重建(慢 1s),数重建次数 ---
R flushall; R set rebuild:cnt 0 >/dev/null; R del cache:hot >/dev/null
NOLOCK='if redis.call("exists","cache:hot")==1 then return "hit" end redis.call("incr","rebuild:cnt") return "rebuild"'
for i in $(seq 1 10); do ( R eval "$NOLOCK" 0; sleep 1; R set cache:hot V >/dev/null ) & done; wait
echo "无锁 重建次数 = $(R get rebuild:cnt)"        # 期望接近 10(惊群)
# --- 互斥:SET NX 抢锁,抢到才重建 ---
R set rebuild:cnt 0 >/dev/null; R del cache:hot lock:hot >/dev/null
MUTEX='if redis.call("exists","cache:hot")==1 then return "hit" end if redis.call("set","lock:hot","1","nx","ex","5") then redis.call("incr","rebuild:cnt") return "rebuild" else return "wait" end'
for i in $(seq 1 10); do ( R eval "$MUTEX" 0 ) & done; wait
echo "互斥 重建次数 = $(R get rebuild:cnt)"        # 期望 1
```

- [ ] **Step 2: 跑并填实机**(期望:无锁≈10、互斥=1)。落差点:`SET NX` 把「N 个并发回源」压成「1 个重建 + N-1 个等待」;锁要带 `EX` 防重建方崩溃后死锁(引出 07 章锁)。
- [ ] **Step 3: Commit** `redis-handson: scenario 06-02 击穿 SET NX 互斥重建`

---

### Task 4: Scenario 03 — 雪崩:TTL 同时过期 vs 随机抖动

**Files:** Create `redis-handson/06-caching-patterns/scenarios/03-avalanche-ttl-jitter.md`

- [ ] **Step 1: 写 scenario**。问题:1000 个 key 都设 `EX 10` vs `EX 10+rand(0,10)`,10 秒后同一秒内过期的数量差多少?用 `EXPIRETIME` 看到期时间分布。可跑步骤:

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
# 固定 TTL:1000 key 全 EX 100
{ for i in $(seq 1 1000); do echo "SET fixed:$i v EX 100"; done; } | docker compose exec -T redis redis-cli --pipe >/dev/null
# 抖动 TTL:EX 100 + 0..100 随机
{ for i in $(seq 1 1000); do echo "SET jit:$i v EX $((100 + RANDOM % 100))"; done; } | docker compose exec -T redis redis-cli --pipe >/dev/null
# 统计到期「秒」去重数:用单个 Lua 扫(不要 1000 次 docker exec,那要 ~200s)
DISTINCT='local s={} for i=1,1000 do local t=redis.call("expiretime",KEYS[1]..i) if t>0 then s[t]=1 end end local c=0 for _ in pairs(s) do c=c+1 end return c'
echo "固定TTL 到期秒去重数(越小=越扎堆): $(R eval "$DISTINCT" 1 fixed:)"
echo "抖动TTL 到期秒去重数(越大=越分散): $(R eval "$DISTINCT" 1 jit:)"
```

- [ ] **Step 2: 跑并填实机**(实测:固定 TTL=**1** 个到期秒(1000 key 全挤同一秒),抖动后=**100** 个秒值)。落差点:同一秒过期数从「1000」摊薄到「~10」;抖动是最便宜的雪崩防护;注意用 Lua 单次扫,别循环 docker exec。
- [ ] **Step 3: Commit** `redis-handson: scenario 06-03 雪崩 TTL 随机抖动`

---

### Task 5: Scenario 04 — 一致性:先删缓存脏读复现 + 延迟双删

**Files:** Create `redis-handson/06-caching-patterns/scenarios/04-consistency-delete-order.md`

- [ ] **Step 1: 写 scenario**。问题:「先删缓存再更 DB」在并发读写下能否留下「缓存=旧、DB=新」的脏数据?延迟双删能否修复?用 `db:k` 当 DB 源,sleep 强制交错。可跑步骤(确定性复现):

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
# 初始:db 和 cache 都是 OLD
R flushall; R set db:k OLD >/dev/null; R set cache:k OLD >/dev/null
# 写线程(先删缓存策略):删缓存 -> (慢)更DB
( R del cache:k >/dev/null; sleep 0.4; R set db:k NEW >/dev/null ) &
# 读线程:稍晚启动,miss 后读到旧 DB(此时写还没更DB),回填旧值
( sleep 0.1; if [ "$(R exists cache:k)" = "0" ]; then v=$(R get db:k); sleep 0.5; R set cache:k "$v" >/dev/null; fi ) &
wait
echo "先删缓存: db=$(R get db:k) cache=$(R get cache:k)"   # 期望 db=NEW cache=OLD(脏!)
# --- 延迟双删修复:写线程更DB后,延迟再删一次缓存 ---
R flushall; R set db:k OLD >/dev/null; R set cache:k OLD >/dev/null
( R del cache:k >/dev/null; sleep 0.4; R set db:k NEW >/dev/null; sleep 0.8; R del cache:k >/dev/null ) &
( sleep 0.1; if [ "$(R exists cache:k)" = "0" ]; then v=$(R get db:k); sleep 0.5; R set cache:k "$v" >/dev/null; fi ) &
wait
echo "延迟双删: db=$(R get db:k) cache=$(R get cache:k)"   # 期望 db=NEW,cache 被二次删除->下次读重建为 NEW
echo "  二次删除后 cache 是否存在: $(R exists cache:k)(0=已删,下次读回填NEW)"
```

- [ ] **Step 2: 跑并填实机**(期望:先删缓存 → cache=OLD/db=NEW 脏读复现;延迟双删 → cache 被二次删除,exists=0,下次读回填 NEW)。落差点:脏读窗口真实存在;延迟双删的「延迟」要 > 读回填耗时才盖得住;根因是「读的回填」和「写的删除」乱序——这也是为什么 Cache-Aside 推荐「先更 DB 后删缓存」(把窗口缩到最小)。
- [ ] **Step 3: Commit** `redis-handson: scenario 06-04 一致性 先删缓存脏读+延迟双删`

---

### Task 6: 面试卡 — 穿透/击穿/雪崩

**Files:** Create `redis-handson/99-interview-cards/q-cache-penetration-breakdown-avalanche.md`

- [ ] **Step 1: 写卡**:一句话区分三者(查不存在 / 单热key失效 / 大批失效)+ 解法表(布隆·空值 / 互斥·逻辑过期·永不过期 / TTL抖动·多级·熔断)+ 链回 scenario 01/02/03 + 易追问(布隆假阳性、为什么逻辑过期不用真过期)。
- [ ] **Step 2: Commit** `redis-handson: 面试卡 穿透击穿雪崩`

---

### Task 7: 面试卡 — 缓存一致性与更新顺序

**Files:** Create `redis-handson/99-interview-cards/q-cache-consistency-update-order.md`

- [ ] **Step 1: 写卡**:一句话(先更DB后删缓存 + 最终一致)+ 四种顺序对比(先删/后删 × 缓存/DB)+ 延迟双删 + binlog 兜底 + 链回 scenario 04 + 易追问(为什么不是先写缓存、强一致怎么办)。
- [ ] **Step 2: Commit** `redis-handson: 面试卡 缓存一致性更新顺序`

---

## Self-Review
- **Spec 覆盖**:对应 spec §06(Cache-Aside/读写穿透回写 + 一致性 + 穿透击穿雪崩 + 布隆/逻辑过期/互斥重建)。✅
- **可跑性**:4 个 scenario 全部 cli + Lua + bash 后台并发,无需额外 DB/runtime;Java/redis-py 仅 README 参考片段。执行时若某 scenario 实跑结果与「期望」不符,以实机为准改 README/落差(这正是方法论核心)。
- **占位**:README 段落在执行时展开;scenario 预期空格刻意留给学习者。
- **命名一致**:`db:k`/`cache:k`/`lock:hot`/`rebuild:cnt`/`bf` 在 scenario 与卡片间一致。

**下一步**:执行本 plan(README → sc01→04 → 2 张卡),逐 scenario 实跑验证,完成后 checkpoint。
