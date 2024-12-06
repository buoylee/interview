## 概述

kafka 的 **broker 只有异步刷盘**, **即使返回成功**, **无法保证不丢**, 只能**靠多副本来提高不丢的机率**. 这就和**rocketmq不同的点**.

## 参考

[刨根问底: Kafka 到底会不会丢数据？](https://www.51cto.com/article/707006.html)

[Can a message loss occur in Kafka even if producer gets acknowledgement for it?](https://stackoverflow.com/questions/57987591/can-a-message-loss-occur-in-kafka-even-if-producer-gets-acknowledgement-for-it)



