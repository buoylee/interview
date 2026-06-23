# 实验 e08 · 读懂信号 —— 饱和度如何领先于延迟报警

> 对应章节 [08 在线监控并发](../../08-monitoring-concurrency/)。证明:在途数/拒绝数(饱和度)在 P99 还没炸时就开始动——这就是「领先指标」,告警该建在这儿。

## 目的

一边压、一边读 `/stats`,亲眼看 `L=λW` 的活体读数:`in_flight`(在途数 L)、`max_in_flight`(高水位)、`rejected`(shed 计数)在延迟雪崩**之前**就抬头,印证 `08 §3`「饱和度领先于利用率/延迟」。

## 跑什么

开三个终端(或用 `&` + `watch`):

```bash
cd concurrency-capacity/lab/service
POOL_SIZE=8 uvicorn app:app --port 8000 --workers 1 &

# 终端 2:持续读信号
watch -n 0.3 'curl -s http://127.0.0.1:8000/stats'

# 终端 3:逐级加压
python drive.py --url 'http://127.0.0.1:8000/slow?ms=50' --steps 80,140,160,200 --seconds 5
```

## 你会看到什么

随着 RPS 逼近池能力(160):

- `in_flight` 先稳步爬升,逼近 `pool_size=8`——**这是负载侧的直接读数,L→容量上限**。
- `max_in_flight` 记录高水位,提示突发瞬时并发。
- 越过拐点,`rejected` 开始跳动,**而此时 drive 报的 P99 可能才刚抬头**——饱和信号比延迟信号**早**。

## 为什么

`in_flight` 和 `rejected` 是 `08` 说的**饱和度/领先指标**:它们直接反映「池容量用了多少、开始拒了没」,在排队恶化的**最早期**就动。而 P99 延迟要等队列真堆起来才飙、CPU 利用率更滞后。**所以生产告警的优先级是:饱和度 > 错误率 > 延迟 > 利用率**——把告警建在 `in_flight`/队列深度上,你能在用户感知到慢之前就收到信号、提前扩容(`09` 的自动扩缩正是按这些信号触发)。

> `/stats` 的三个字段就是一套最小化的并发监控埋点;生产里把它们吐成 Prometheus 指标(`08` 三语速记),配 Grafana + 告警。

> 收尾:`pkill -f "uvicorn app:app --port 8000"`
