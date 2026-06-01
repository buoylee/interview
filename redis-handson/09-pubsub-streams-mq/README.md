# pub/sub vs List vs Stream（用 Redis 当消息队列）

## 1. 核心问题

Redis 有三种「消息传递」方式:**pub/sub**、**List**、**Stream**。本章讲清三者怎么用、各丢不丢消息、能不能多消费者分组消费/ack/重放,以及——**什么时候该用 Redis 当 MQ、什么时候老老实实上 Kafka/RabbitMQ**。

## 2. 直觉理解

- **pub/sub**=广播喇叭:发出去时谁在听谁收到,**没订阅者就丢、订阅者掉线就漏**(fire-and-forget,不持久)。
- **List**=一根管子:`LPUSH` 进、`BRPOP` 出,消息被**消费一次就没了**;能当简单队列,但没有「消费组 / ack / 重放」。
- **Stream**=正经的消息日志:消息**持久**追加,支持**消费组**(多消费者分摊)、**ack**(确认消费)、**PEL**(未确认列表)、**重放/接管**(消费者崩了别人 `XAUTOCLAIM` 接手)、**trim**(限长)。是 Redis 当 MQ 的正主。

## 3. 原理深入

### 3.1 pub/sub
- `SUBSCRIBE ch` / `PUBLISH ch msg`。`PUBLISH` 返回**当前收到的订阅者数**。
- **不持久、不可靠**:sc01 实测,无订阅者时 `PUBLISH` 返回 0——消息直接丢;订阅者断线重连,断线期间的消息也漏。
- 适合:实时通知、配置推送等「丢了无所谓、要的是即时广播」的场景。

### 3.2 List 当队列
- 生产 `LPUSH`,消费 `BRPOP`(阻塞弹出)。消息被弹出即从 List 删除——**消费一次、点对点**。
- 缺点:没有消费组(多个消费者是竞争,不是各自一份)、没有 ack(弹出后消费者崩了消息就丢)、不能重放。
- 适合:简单的「单一消费者/竞争消费」任务队列,要求不高时。

### 3.3 Stream（XADD / 消费组 / PEL / ack / XAUTOCLAIM）
- `XADD key * field val`:追加消息(`*` 自动生成 `<ms>-<seq>` id),**持久**。`XLEN`、`XRANGE` 可回看。
- **消费组**:`XGROUP CREATE key group <id>`;`XREADGROUP GROUP g consumer COUNT n STREAMS key >` 读**未投递**的新消息,组内多消费者**分摊**(各拿不同消息)。
- **PEL(Pending Entries List)**:被某消费者读走但**还没 `XACK`** 的消息进 PEL;`XPENDING` 查。
- **`XACK`**:确认消费,从 PEL 移除。没 ack 的消息一直在 PEL（消费者崩了不丢）。
- **`XAUTOCLAIM`/`XCLAIM`**:消费者崩溃后，别的消费者把它 PEL 里滞留太久的消息**接管**过来重新处理(死信/重投递)。sc02 实测:A 读了不 ack,B `XAUTOCLAIM` 接管了 A 的滞留消息。
- **trim**:`XADD ... MAXLEN [~] n` 或 `XTRIM` 限制长度,防无限增长(sc02 实测 MAXLEN 10 把流裁到 10)。

## 4. 日常开发应用

- **实时广播、丢了无所谓** → pub/sub。
- **简单任务队列、单消费者** → List(`LPUSH`+`BRPOP`)。
- **要可靠、要消费组分摊、要 ack/重放** → Stream。
- **要超高吞吐、长期堆积、严格顺序分区、回溯消费** → 别硬用 Redis,上 **Kafka**;要复杂路由/事务 → RabbitMQ。Redis Stream 适合「中小规模、想少引一个组件」的可靠队列。

## 5. 调优实战

- **Stream 无限涨** → 一定配 `MAXLEN ~`(近似裁剪,带 `~` 性能更好)或定期 `XTRIM`。
- **消息卡在 PEL 不消费** → 消费者崩了没 ack;靠 `XAUTOCLAIM` + min-idle-time 做重投递/死信。
- **pub/sub 丢消息投诉** → 它本来就不可靠;换 Stream。
- **List 队列消息丢** → `BRPOP` 弹出后崩溃就丢;要可靠用 Stream(有 PEL+ack)。

## 6. 面试高频考点

- **pub/sub vs Stream?** pub/sub 不持久/掉线丢(sc01);Stream 持久 + 消费组 + ack + 重放。
- **List 当 MQ 的缺陷?** 无消费组、无 ack、弹出即删不能重放;消费者崩在「已弹出未处理」会丢。
- **Stream 消费者崩了消息丢吗?** 不丢,在 PEL 里;`XAUTOCLAIM` 让别的消费者接管(死信)。
- **Redis Stream vs Kafka?** Stream 轻量、够中小规模可靠队列;超高吞吐/海量堆积/严格分区顺序用 Kafka。

## 7. 一句话总结

**pub/sub** 广播不可靠(掉线即丢);**List** 简单队列(消费一次、无 ack/组);**Stream** 才是 Redis 的可靠 MQ(持久 + 消费组 + PEL + ack + `XAUTOCLAIM` 重投递 + MAXLEN trim)。要可靠用 Stream,要超高吞吐/回溯上 Kafka。

## Scenarios

- [01 - pub/sub 丢消息 vs Stream 持久不丢](scenarios/01-pubsub-loss-vs-stream.md)
- [02 - Stream 消费组:读/PEL/ack/XAUTOCLAIM/trim](scenarios/02-stream-consumer-group.md)
