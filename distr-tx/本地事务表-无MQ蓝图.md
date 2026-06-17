# 本地事务表 — 无 MQ 可复用蓝图(事件式 outbox)

> 用一张**本地表**,把「业务变更」和「待传播的事件」放进**同一个本地事务**,实现跨边界最终一致——**不依赖任何 MQ**。
> 语言/DB 中立。任意项目要落地时翻译成具体语言即可;也可直接当面试话术复述。
>
> 配套:数据库选型见 [`../DB/数据库选型.md`](../DB/数据库选型.md);金融域 + Kafka 路线的完整实现见 [`../financial-consistency/`](../financial-consistency/)。

---

## 一、这是什么 + 它在整张图里的位置

「本地事务表」= 「本地消息表」=「outbox 表」,三个名字同一个东西。要看清它,把整件事拆成**三根独立的轴**:

```text
轴1【写侧:怎么防双写】 → 本地事务表 / outbox 表
                         (业务变更 + 事件行,同一本地事务原子落库)
                         ★ 这一轴是本蓝图的核心,所有可靠方案都共用它

轴2【搬运:怎么排空这张表】→ (a) 定时器轮询(Polling)   ← 本蓝图用这个
                          (b) CDC 监听 binlog(Canal/Debezium,需额外中间件)

轴3【投递:事件发去哪】   → (a) 直接派发给本地 handler(无 MQ)  ← 本蓝图默认
                          (b) 发到 MQ,消费者订阅            ← 留好的升级口
```

**本蓝图 = 轴1(本地事务表)+ 轴2(轮询)+ 轴3(默认直接派发,可插拔换 MQ)。** 它就是「不依赖任何中间件、只用你现有的 DB」的最小可靠落地方式;同时把轴3 抽象成可插拔接口,以后要上 MQ 只换一处。

> 这个模式有名字:Chris Richardson 的 **Polling Publisher**;国内分布式事务语境里就叫**本地消息表**。它不是 hack,是教科书级方案。

## 二、动手前先问:你是不是根本不需要它

资深的第一反应是**砍需求**,而不是套方案。按顺序问:

1. **这个冗余/派生数据是「快照」还是「活引用」?**
   - **快照**(下单时的买家名、成交价、商品标题):记录的是**当时**的事实,用户后来改名,历史订单**就该**显示旧名。→ **根本不传播**,改了反而是 bug。
   - **活引用**(信息流里要跟当前昵称一致的作者名):才需要「源头变 → 副本跟着变」。
   - 经验:大量「冗余」其实是快照,不需要任何同步。先把这一刀切掉。

2. **这两份数据能不能放进同一个库、同一个本地事务?**
   - 能 → 直接用一个本地事务,**连本蓝图都不需要**,更别提最终一致。
   - 别过早拆服务/拆库,制造出本不存在的分布式一致性问题。

只有当「确实跨了边界(服务/库)+ 确实是活引用要传播」时,才进入本蓝图。

## 三、它解决的问题:双写问题(dual-write)

跨边界时不能用本地事务,最容易踩的坑是:

```text
应用先改源头(成功) → 再调下游改副本(网络抖动失败)
                                    ↑ 两边不一致,且第一步没法回滚
```

本蓝图的根治办法:**把「改业务」和「记事件」做成原子**——同一个本地事务里,既写业务表,也写 outbox 事件行。只要本地事务提交成功,事件一定在表里,后续投递失败可无限重试;本地事务回滚,事件也不会留下。

## 四、何时该升级到 MQ(写成判据,不靠感觉)

无 MQ 版是**首选**,不是将就。但撞到下面任意一条,才把投递器换成 MQ:

| 触发条件 | 为什么 MQ 更合适 |
|---|---|
| **扇出**:一个事件要发给 3+ 且增长的消费者 | 轮询+直连要生产方知道每个下游,耦合爆炸;MQ 发布订阅天然解耦 |
| **吞吐**:轮询频率高到打满 DB | DB 成瓶颈;MQ 为高吞吐而生 |
| **削峰**:下游慢/尖刺,要缓冲 | MQ 当 buffer,生产方不被拖住 |
| **跨团队解耦**:不想知道谁消费 | 组织级解耦 |
| **已经有 MQ 在跑** | 边际成本≈0,直接用(甚至 RocketMQ 事务消息可省掉本地表) |

判据之外硬上 MQ,就是 resume-driven 的过度设计。

---

## 五、架构(4 个角色)

```text
[Producer] --同一本地事务--> 业务表 + outbox_event(PENDING)
                                  │
                         [Relay 轮询器] 认领 PENDING
                                  │
                         [Dispatcher 投递器] 按 event_type 派发   ← 那条「缝」
                                  │
                    [Handler(s)] 执行(直调下游 / 改副本)—— 必须幂等
                                  │
                       标记 DONE / 退避重试 / DEAD
```

- **Producer**:业务方。写业务事实 + 写事件,**同一本地事务**。
- **Relay 轮询器**:独立进程/线程,周期性认领 `PENDING` 事件,交给 Dispatcher。
- **Dispatcher 投递器**(可插拔):默认本地按 `event_type` 派发给已注册 handler;升级版发 MQ。
- **Handler**:消费方逻辑,**必须幂等**。

## 六、数据模型(DB 中立)

```text
outbox_event
  id            主键(自增 / 雪花;且 = 投递顺序)
  event_type    事件类型,如 'user.renamed'
  aggregate_id  实体 id(有序边界 / 分区键)
  payload       事件数据(JSON)
  status        PENDING / PROCESSING / DONE / DEAD
  version       事件版本号(幂等 & 乱序守卫)
  retry_count   已重试次数
  next_retry_at 到点才捞(退避)
  created_at
  updated_at
  last_error    最后一次失败原因(排障)
  INDEX (status, next_retry_at)   -- 捞任务的索引
```

消费侧幂等,二选一:
- **处理记录表** `processed_event(consumer, event_id)` 加唯一约束:插过就跳过。
- **版本守卫**:目标行存 `version`,只在「来的版本 > 现存版本」时才应用。

## 七、状态机

```text
PENDING ─认领→ PROCESSING ─成功→ DONE
                   ├ 失败 & retry < MAX → PENDING(next_retry_at = now + backoff)
                   └ 失败 & retry ≥ MAX → DEAD(告警,转人工)
```

## 八、核心流程(伪代码)

### 写入端 — 原子入队

```text
# 关键:业务变更和事件,在同一个本地事务里
begin_local_transaction:
    update 业务表 ...
    insert outbox_event(event_type, aggregate_id, payload,
                        status=PENDING, version=v, next_retry_at=now)
commit            # 要么都成,要么都不成 → 杜绝双写
```

### 轮询器 — 认领与派发

```text
loop every N seconds:
    # 认领一批(并发安全见铁律③)
    batch = SELECT * FROM outbox_event
            WHERE status='PENDING' AND next_retry_at <= now
            ORDER BY id
            LIMIT B
            FOR UPDATE SKIP LOCKED          # 并发 worker 不抢同一行
    mark batch as PROCESSING

    for e in batch:
        try:
            dispatcher.dispatch(e)          # 默认 = 直接调本地 handler
            set e.status = DONE
        catch err:
            e.retry_count += 1
            e.last_error = err
            if e.retry_count >= MAX:
                e.status = DEAD             # 进死信,告警
            else:
                e.status = PENDING
                e.next_retry_at = now + backoff(e.retry_count)   # 指数退避
```

## 九、五条可靠性铁律(蓝图的灵魂,每条都讲清「为什么」)

之所以很多人「想到这个方案就觉得风险高、最后不了了之」,是因为下意识想做「**恰好一次 + 全局有序**」——那两个恰恰是不该追的。松开它们,方案从「不敢上线」变成「一下午能写完」。

**① 原子入队**
业务 + 事件同一本地事务。→ 根除双写问题(第三节)。

**② 至少一次 + 幂等(最重要,也最能消除恐惧)**
轮询器一定会偶尔把一个事件执行两次(干完活、还没标 DONE 就崩了,重启又捞到)。**不要追求 exactly-once——分布式做不到。要让重复执行无害**:用版本守卫 / 唯一约束 / 业务幂等键去重。想通这条,80% 的恐惧就没了:崩了重跑也不会错。

**③ 并发认领安全**
多个 worker(或上一轮没跑完又起一轮)不能抢同一行。
- 首选 `SELECT … FOR UPDATE SKIP LOCKED`(PostgreSQL / MySQL 8):锁住并跳过别人正在处理的行。
- 老库(MySQL 5.7 无 SKIP LOCKED)用**状态 CAS**:`UPDATE … SET status='PROCESSING' WHERE id=? AND status='PENDING'`,看影响行数是不是 1,抢到才处理。

**④ 重试 + 指数退避 + 死信**
失败 `retry_count++`、`next_retry_at = now + 退避`;超过 MAX 转 `DEAD` 并**告警人工**。别让毒任务在循环里把 DB 打爆。

**⑤ 放弃全局有序(这是「想到放弃」的真正陷阱)**
- 大多数场景**只需「同一实体内有序」**,不需要全局有序。用②的**版本守卫**(只接受更高版本),乱序到达也能自我纠正:A→B 乱成 B→A,B 版本更高,A 来了直接丢弃,结果照样对。
- 真要某实体严格串行:单 worker,或按 `aggregate_id` 哈希分片、一个 worker 包干一个分片。
- 砍掉「全局有序」,难度立刻从地狱降到普通。

## 十、投递器:那条「升级 MQ」的缝

```text
interface Dispatcher:
    dispatch(event) -> ok / throw

# 默认实现:无 MQ,本地直接派发
LocalDispatcher:
    handlers = { event_type -> [handler, ...] }   # 注册表
    dispatch(e):
        for h in handlers[e.event_type]:
            h(e)                                   # 直接调用,必须幂等

# 升级实现:发 MQ(以后撞到第四节触发条件时才换)
MqDispatcher:
    dispatch(e):
        broker.publish(topic(e.event_type), e)
```

切换只换 `Dispatcher` 实现 + 配置:**Producer / Relay / 状态机 / schema 全不动**。这就是「为升级留缝,但现在不付成本」——演进式架构。

> 事件式(行 = 「发生了什么」)而非命令式(行 = 「要做什么」),正是为了让这条缝几乎免费:MQ 本就是发布订阅,事件天然契合;命令式则要把「命令」重新理解成「事件」,缝不自然。

## 十一、可观测 / 运维(production-ready 的部分)

- **指标**:`PENDING` 积压数、`DEAD` 数、重试次数分布、投递延迟(now − created_at)。
- **排障**:`last_error` 字段 + `DEAD` 告警。
- **运维口**:单条重投(`DEAD → PENDING`)、批量重投——一个内部 API 或一条 SQL 都行。
- **清理**:`DONE` 事件定期归档/删除,防表无限膨胀。
- **对账兜底**:再可靠的投递也会漏。周期性扫「源头事实 vs 已传播」,找不一致并修复——心态是「保证最终收敛 + 自愈」,不是「永不出错」。

## 十二、验证清单(怎么证明它对)

- 提交后、投递前**杀进程** → 重启能补投(证明②原子 + 可恢复)。
- handler 持续失败 → 退避重试,超限进 `DEAD`(证明④)。
- 同一事件**投两次** → 业务只发生一次(证明②幂等)。
- **并发多 worker** → 不重复认领同一行(证明③)。
- 事件**乱序到达** → 版本守卫下结果仍正确(证明⑤)。

---

## 十三、面试话术

**整体判断阶梯**(被问「怎么保证跨服务一致性」时,按顺序讲,显资深):
1. 先砍需求:是快照吗?能不能放进一个本地事务?——大半问题在这步消失。
2. 真要跨边界传播,我默认用**本地事务表 + 轮询 + 直接派发**,零额外中间件,可靠性保证和 MQ 一样。
3. 只有出现**扇出 / 吞吐打满 DB / 削峰 / 跨团队**,我才引 MQ;而且事件的产生和投递解耦,留好升级口。
4. 配**对账 job** 兜底。

**为什么敢不用 MQ**:MQ 不是 outbox 的本质,本质是「业务+事件原子落库 + 一个可靠搬运工」。搬运工可以是 Kafka,也可以是定时器。MQ 多给的是扇出和吞吐,不是更强的一致性。对中小团队,自养一套 Kafka 的运维税,往往比这张表的成本高得多。

**四条铁律一句话**:原子入队、至少一次+幂等、SKIP LOCKED/CAS 认领、退避+死信;外加「放弃全局有序、用版本守卫」。

**关于「现实里大家都上 MQ」**:那多半是因为公司**本来就有** MQ(用它边际成本≈0),不是专门为一致性硬补一个。分清「已经铺好的路」和「要新养的依赖」,才是资深。

## 关联阅读

- 数据库选型(关系型/Mongo/ES、分片后处理关联):[`../DB/数据库选型.md`](../DB/数据库选型.md)
- 金融域 + Kafka 路线的完整实现与对账:[`../financial-consistency/`](../financial-consistency/)
- Outbox 概念(金融语境、预设 broker):[`../financial-consistency/05-patterns/02-outbox-local-message-table.md`](../financial-consistency/05-patterns/02-outbox-local-message-table.md)
- 本地消息表 vs 事务 MQ:[`../MQ/distr-tx基于mq/本地消息表-and-事务mq.md`](../MQ/distr-tx基于mq/本地消息表-and-事务mq.md)
