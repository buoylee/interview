# Redis 当消息队列:pub/sub、List、Stream 怎么选？

## 一句话回答

**pub/sub** 广播不可靠(掉线/无订阅者即丢、不持久);**List**(`LPUSH`/`BRPOP`)简单点对点队列(消费一次、无 ack/消费组/重放);**Stream** 才是可靠 MQ(持久 + 消费组分摊 + PEL + ack + `XAUTOCLAIM` 重投递 + MAXLEN trim)。要可靠用 Stream,要超高吞吐/回溯上 Kafka。

## 三者对比

| | 持久 | 消费组 | ack/重投递 | 重放 | 适合 |
|---|---|---|---|---|---|
| pub/sub | ❌ | ❌ | ❌ | ❌ | 实时广播(丢了无所谓) |
| List | ✅(在队列里) | ❌(竞争) | ❌(弹出即删) | ❌ | 简单任务队列 |
| Stream | ✅ | ✅ | ✅(PEL+XACK) | ✅(XRANGE) | 可靠消息队列 |

## 实测证据

- pub/sub 无订阅者 `PUBLISH`=0(丢);Stream `XADD` 持久,过后 `XRANGE` 照读。[sc01](../09-pubsub-streams-mq/scenarios/01-pubsub-loss-vs-stream.md)
- Stream:A 读不 ack → XPENDING=2(在 PEL 没丢);B `XAUTOCLAIM` 接管;`XACK` 后降 1;`MAXLEN 10` 把流裁到 10。[sc02](../09-pubsub-streams-mq/scenarios/02-stream-consumer-group.md)

## 易追问的延伸

- **Stream 消费者崩了消息丢吗?** 不丢,在 PEL;`XAUTOCLAIM`(配 min-idle-time)让别的消费者接管 = 死信/重投递。
- **List 当队列的丢消息点?** `BRPOP` 弹出后、处理完成前崩溃 → 消息已离队却没处理完 → 丢(无 ack)。
- **Stream 怎么防无限涨?** `XADD MAXLEN ~ n`(近似裁剪更快)或定期 `XTRIM`,否则成大 key(12 章)。
- **Redis Stream vs Kafka?** Stream 轻量够中小规模可靠队列;海量堆积/超高吞吐/严格分区顺序/长期回溯用 Kafka。

## 证据链接

- 章节原理:[09-pubsub-streams-mq](../09-pubsub-streams-mq/README.md)
- 实测:[sc01 pub/sub vs Stream](../09-pubsub-streams-mq/scenarios/01-pubsub-loss-vs-stream.md)、[sc02 Stream 消费组](../09-pubsub-streams-mq/scenarios/02-stream-consumer-group.md)
