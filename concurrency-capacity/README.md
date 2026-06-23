# 并发容量工程 —— 从需求数字到站得住脚的配置

> 把一句业务需求(*"10k RPS,P99 < 200ms"*)翻译成**能在评审上站得住脚的配置**:用哪种并发模型、单机配多大、每个池开多少、要不要隔离、盯哪几个信号、要几台机器——并且**知道每个数字为什么是这个数字**。
>
> 这是「我会用并发原语」到「我能给系统定容」之间那一层工程学。资深 → 架构师向。

## 这门课填的缺口

你大概已经会用线程、协程、goroutine 了。但到了真实环境,面对「这个服务该怎么配」时还是抓瞎——因为这一层**散落在三门课之间,从没被拼成一条决策管线**:

| 已有的课 | 教什么 | 为什么不是这一层 |
|---|---|---|
| `python-concurrency/09` · `golang/concurrency` · `java/concurrent` | 并发**原语**:线程/协程/池/Semaphore | 给你**武器**,不教**用兵法**——"池大小最终压测定",给了旋钮没教「事前怎么算这个数」 |
| `performance-tuning-roadmap/` | 剖析、压测、调试(py-spy/pprof/wrk) | **反应式**——出事后怎么找瓶颈;这门课问的是**事前**怎么定容 |
| `system-design/` | 宏观分布式架构(分片/共识/CAP) | 高一个高度;不是「这一个服务开几个线程」 |

缺的正是中间这层:**容量与并发工程**。这门课把它补上。

## 主线:一条 Little 定律,贯穿全程

你不会遇到 12 个互不相干的话题,而是遇到**一个方程**,看着每个生产问题从它身上掉下来:

$$L = \lambda \times W \quad(\text{在途数} = \text{到达率} \times \text{停留时间})$$

- *测算并发需求* → `λ × W` 直接给出
- *池多大 / 多少线程* → 所需并发 ÷ 单 worker 容量
- *单机配置* → 利用率在哪饱和
- *是否隔离* → 哪些工作负载共享一个池而互相饿死
- *是否监控* → 利用率 / 饱和度 / 队列深度,就是这个方程的**实时读数**

一条主线 = 系统性 + 阅读流畅性。先去 `01` 把这把钥匙认下来。

## 章节地图

| 章 | 主题 | 干掉的问题 |
|---|---|---|
| [`00-decision-pipeline/`](00-decision-pipeline/) | 决策管线全景 | 整条管线长什么样:需求→模型→单机→池→隔离→过载→监控→扩容 |
| [`01-littles-law/`](01-littles-law/) | **Little 定律(总钥匙)** | 你缺的「系统性认知」:`L=λW`、利用率、饱和曲线、为什么 P99 会拐 |
| [`02-concurrency-models/`](02-concurrency-models/) | 三种并发模型 | **正确的并发模型怎么选**:thread-per-req / event-loop / 多进程worker |
| [`03-measure-demand/`](03-measure-demand/) | 测算真实并发需求 | **如何测算生产并发需求**:λ、W、峰均比、fan-out 放大 |
| [`04-sizing-one-node/`](04-sizing-one-node/) | 单机配置与线程/worker 数 | **多少线程 + 单机配多大**:线程公式推导、USL 拐点、USE |
| [`05-pools/`](05-pools/) | 池:哪些、多大、×worker 总账 | **哪些需要 pool、pool 多大**:M/M/c、小池更快、总账坑 |
| [`06-isolation/`](06-isolation/) | 隔离 / 舱壁 | **是否需要隔离**:队头阻塞级联、按 快/慢·CPU/IO·租户 拆池 |
| [`07-overload-backpressure/`](07-overload-backpressure/) | 过载与背压 | 过饱和点的雪崩、限流降级、重试风暴、超时即背压 |
| [`08-monitoring-concurrency/`](08-monitoring-concurrency/) | 在线监控并发 | **是否需要监控**:饱和度领先于利用率、USE + RED |
| [`09-scaling-out/`](09-scaling-out/) | 横向扩容与成本 | 单机到机群、何时 scale-out、每 RPS 成本、扩容信号 |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 反向产出的高频题速答 + 深题卡 |

## 怎么用这门课

1. **按 00 → 09 顺序读**。每章一条主线,不是 7 段模板;深层机理(排队论/运行时)写在正文里,不丢给问答。
2. **每章末尾有「动手:跑这个实验」**。`lab/sim/` 是纯 Python、零基建、确定性的——读到饱和曲线时,真的跑一下看它爆炸,比读公式记得牢。
3. **想答面试题** → `99-interview-cards/`,每张卡链回章节做证据。

## 学习环境(两层 lab)

```
lab/
  sim/        # 离线、纯 stdlib、确定性 —— 零基建,每章可跑
    little.py     拨 λ,W → L,ρ,R 的 P99 曲棍球杆          (01)  ✅ 可跑
    saturate.py   扫负载 → 吞吐平台 + USL 回退              (01/04)
    starve.py     池=N → 等待时间爆炸(M/M/c)             (05)
    bulkhead.py   共享池 vs 隔离池                        (06)
  service/    # 真实 FastAPI,带旋钮(模型、池大小),真负载下跑
    app.py / drive.py / compose.yaml
  experiments/  # 每章一份 runbook:跑什么、会看到什么、为什么
```

第一个就能跑:

```bash
cd concurrency-capacity
python lab/sim/little.py --lam 200 --w 0.05
# L = 10 in flight,然后打印 ρ=0.99 时 R 暴涨到 100× 的曲棍球杆
```

## 进度地图

| 部分 | 状态 |
|---|---|
| 设计 spec / 实现计划 | ✅ `docs/superpowers/specs|plans/2026-06-23-concurrency-capacity*` |
| README(本文件) | ✅ |
| `lab/sim/little.py` | ✅ 4 测试通过 |
| 00 决策管线全景 | ✅ |
| 01 Little 定律 | ✅ |
| 02–09 各章 | ⬜ 逐章建设中 |
| `lab/sim/saturate|starve|bulkhead` | ⬜ |
| `lab/service/` + experiments | ⬜ |
| 99 面试卡 | ⬜ |

## 指进已有课(复用不重复)

这门课只指进、不复制已有深矿:

- Little 定律更深的数学 → [`performance-tuning-roadmap/01-methodology/04-performance-laws.md`](../performance-tuning-roadmap/01-methodology/04-performance-laws.md)
- USE 方法 → [`…/01-methodology/02-use-method.md`](../performance-tuning-roadmap/01-methodology/02-use-method.md)
- Python 并发模式 / worker 落地 → [`python-concurrency/09`](../python-concurrency/09-patterns-tuning/) · [`07`](../python-concurrency/07-prod-web-workers/)
- 剖析 / 压测工具 → [`performance-tuning-roadmap/06a`](../performance-tuning-roadmap/06a-python-profiling/) · [`07`](../performance-tuning-roadmap/07-load-testing/) · [`03x`](../performance-tuning-roadmap/03x-load-gen-quickstart/)
- 语言原语 → [`golang/concurrency`](../golang/concurrency/) · [`java/concurrent`](../java/concurrent/)
- OS 层进程/线程/协程 → [`performance-tuning-roadmap/00-os-fundamentals/05`](../performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md)
