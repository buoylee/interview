# 实验 e07 · 过载塌方 —— 过了饱和点,吞吐和延迟一起崩

> 对应章节 [07 过载与背压](../../07-overload-backpressure/)。证明:过载不是「慢一点」,是吞吐塌方 + 延迟雪崩同时发生;有界池的 shed(503)是怎么救命的。

## 目的

把服务推过饱和点(λ>μ),看 `07 §1` 描述的塌方:有效 qps 不升反降、P99 以秒计;同时看 `POOL_SIZE` 的有界拒绝(shed)如何把「全部慢死」变成「快速失败一部分」。

## 跑什么

```bash
cd concurrency-capacity/lab/service
POOL_SIZE=8 uvicorn app:app --port 8000 --workers 1 &     # 池能力 = 8/0.05 = 160 RPS

# 一路压过饱和点
python drive.py --url 'http://127.0.0.1:8000/slow?ms=50' --steps 80,160,320,640 --seconds 3
curl -s http://127.0.0.1:8000/stats     # 看 rejected(被 shed 的数量)
```

## 你会看到什么

```
rps=80    qps≈79    p99≈58ms     errors=0      健康
rps=160   qps≈139   p99≈70ms     errors=少量    拐点
rps=320   qps≈28    p50≈6000ms   errors=600+    ← 塌方:qps 崩,延迟雪崩
rps=640   qps 更低  延迟更长      errors 更多     彻底过载
/stats → rejected 数百            ← 有界池在 shed,没让队列无限堆
```

## 为什么

- 过 160 RPS(=池能力,ρ=1)后,λ>μ,每秒净增 (λ−μ) 个排队请求,队列增长 → 排到的请求客户端早超时(白干)→ **有效 qps 反而塌**(`07 §1`)。
- 那些拿到 503 的请求,是 `POOL_SIZE` 有界 + 满了 shed 的结果——**这正是 `07 §2` 的「有界队列 + 快速失败」**:与其让所有请求排到天荒地老一起烂掉,不如明确拒绝一部分,让客户端早点重试/降级。
- 想象一下如果池**无界**:不会有 503,但 `max_in_flight` 和延迟会一起飙到 OOM/全面超时——这就是为什么无界队列是慢性自杀。

> 进阶思考:这里若叠加客户端「失败重试 3 次」,320 RPS 会被放大成 ~960 RPS 打过来——`07 §3` 的重试风暴。生产中必须配退避+预算+断路器。

> 收尾:`pkill -f "uvicorn app:app --port 8000"`
