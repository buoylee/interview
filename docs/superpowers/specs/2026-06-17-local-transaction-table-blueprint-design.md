# 通用「本地事务表」蓝图设计 spec(无 MQ · 事件式 outbox)

- 日期:2026-06-17
- 类型:可复用方案蓝图(语言/DB 中立)
- 交付物:`distr-tx/本地事务表-无MQ蓝图.md`
- 本 spec:记录设计决策与结构,供写蓝图时遵循

---

## 1. 目标与动机

提供一份**语言/DB 中立、可在任意项目复用**的「本地事务表」方案蓝图,用本地事务表实现跨边界最终一致,**不依赖任何 MQ**。

动机:仓库现有的 `financial-consistency/`(`05-patterns/02-outbox-local-message-table.md`、`11-outbox-publisher/`)是 **金融域 + Kafka 路线** 的实现,预设了 broker。缺一个**通用、不绑域、无 MQ(轮询 + 直接派发)**、中小团队能直接复用的版本。本蓝图补这个缺口,并作为面试可复述资产。

## 2. 范围与非目标

**解决**:防双写、至少一次投递、可靠收敛。

**明确非目标**(写进蓝图,防误用):
- 不是分布式 ACID。
- 不证明下游业务完成(只证明事件已可靠待投/已投)。
- 不替代状态机、账本、对账、人工修复。
- 不提供强一致;提供的是**有界延迟 + 保证收敛 + 自愈**。

**适用场景**:中小规模、无 MQ、单库或同库副本;以及「先无 MQ、以后可能上 MQ」的演进路径。

**升级到 MQ 的触发条件**(写进蓝图当判据):扇出到多消费者 / 吞吐打满 DB / 需要削峰缓冲 / 跨团队解耦。

## 3. 已定的关键决策(brainstorm 结论)

| 决策点 | 选定 | 理由 |
|---|---|---|
| 形态 | 语言中立蓝图(schema + 状态机 + 伪代码 + 取舍 + 面试话术) | 任意语言可翻译落地,且适合面试复述 |
| 架构 | 无 MQ 核心 + 可插拔投递器(Dispatcher)接口 | 为升级 MQ 留缝,但现在不付成本 |
| 行语义 | 事件式(行 = 「发生了什么」) | 解耦好、升级 MQ 几乎零成本、最通用 |
| 顺序 | 默认放弃全局有序,用 version 守卫;需要时按 aggregate_id 串行 | 全局有序是「想复杂到放弃」的陷阱;幂等 + 版本守卫可自我纠正 |
| 重投 | 提供重投能力,API 或 SQL 二选一(蓝图不强绑 API) | 语言中立 |

## 4. 架构与组件(4 角色)

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

- **Producer**:写业务事实 + 写事件,同一本地事务(原子)。
- **Relay**:轮询认领 `PENDING` 事件,交给 Dispatcher。
- **Dispatcher**(可插拔):默认 `LocalDispatcher` = 按 `event_type` 派发给已注册 handler 直接调用;升级 `MqDispatcher` = publish 到 topic。切换只换实现 + 配置,其余不动。
- **Handler**:消费方逻辑,**幂等**。

## 5. 数据模型(DB 中立)

```text
outbox_event
  id            主键(自增/雪花,且 = 投递顺序)
  event_type    'user.renamed'
  aggregate_id  实体 id(有序边界 / 分区键)
  payload       JSON
  status        PENDING / PROCESSING / DONE / DEAD
  version       幂等 & 乱序守卫
  retry_count   重试次数
  next_retry_at 到点才捞(退避)
  created_at / updated_at
  last_error    最后失败原因(排障)
  INDEX (status, next_retry_at)   -- 捞任务
```

消费侧幂等二选一:`processed_event(consumer, event_id)` 唯一约束;或目标行 `version` 守卫(只接受更高版本)。

## 6. 状态机

```text
PENDING ─认领→ PROCESSING ─成功→ DONE
                   ├ 失败 & retry<MAX → PENDING(next_retry_at = now + backoff)
                   └ 失败 & retry≥MAX → DEAD(告警,人工)
```

## 7. 五条可靠性不变量(蓝图核心,每条配「为什么」)

1. **原子入队**:业务 + 事件同一本地事务 → 根除双写问题。
2. **至少一次 + 幂等**:不追求 exactly-once(分布式做不到);让重复执行无害(version 守卫 / 唯一约束 / 幂等键)。
3. **并发认领安全**:`SELECT … FOR UPDATE SKIP LOCKED`(PG / MySQL 8);老库(MySQL 5.7)用状态 CAS(`UPDATE … SET status='PROCESSING' WHERE id=? AND status='PENDING'` 看影响行数)。两种都写。
4. **重试 + 指数退避 + 死信**:封顶 + 退避 + DEAD 告警,不无限空转。
5. **放弃全局有序**:用 version 守卫;真要顺序就按 `aggregate_id` 串行(单 worker 或按 id 哈希分片)。

## 8. 可观测 / 运维(production-ready)

- **指标**:pending 积压、DEAD 数、重试分布、投递延迟。
- **排障**:`last_error` 字段 + DEAD 告警。
- **运维口**:单条重投(DEAD→PENDING)、批量重投(API 或 SQL)。
- **清理**:DONE 事件定期归档/删除,防表膨胀。

## 9. 验证清单

- 提交后、投递前杀进程 → 重启能补投。
- handler 失败 → 退避重试,超限进 DEAD。
- 同事件投两次 → 业务只发生一次(幂等)。
- 并发多 worker → 不重复认领同一行。

## 10. 交付物结构与放置

- **正式蓝图** → `distr-tx/本地事务表-无MQ蓝图.md`(`distr-tx/` 已有 CRDT、SEATA,是分布式事务模式的家)。
- 章节顺序:定位与边界 → 架构 → schema → 状态机 → 五条不变量(配 why)→ 投递器缝 → 可观测/运维 → 验证清单 → **面试话术**(为什么不用 MQ / 何时升级 / 四条铁律 / 放弃全局有序)→ **关联阅读**(`financial-consistency/`、`DB/数据库选型.md`)。

## 11. 实现说明

交付物是单篇语言中立蓝图(markdown),非代码工程。实现步骤 = 按本 spec 第 10 节结构,把第 4–9 节内容展开成可教学、可面试复述的蓝图文档。无需独立的 writing-plans 工程化拆分。
