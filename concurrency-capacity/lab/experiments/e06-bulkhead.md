# 实验 e06 · 舱壁隔离 —— 慢负载饿死快负载,以及隔离如何挡住

> 对应章节 [06 隔离/舱壁](../../06-isolation/)。证明:共享池里一个慢负载能饿死毫不相干的快负载;隔离后快路毫发无伤。

## 目的

亲眼看队头阻塞级联(`06 §2`):共享池被慢请求占满 → 快请求被拒;再看隔离把快路保护住。

## 跑什么

### A. 离线、确定性(秒出对比)

```bash
cd concurrency-capacity
python lab/sim/bulkhead.py
```

### B. 真实服务(慢端点拖垮快端点)

```bash
cd concurrency-capacity/lab/service
# 共享小池:/fast 和 /slow 抢同一个 POOL... 注意:本 demo 的 /fast 不占池,
# 用 /slow?ms=2000(慢)和 /slow?ms=10(快)共用 POOL_SIZE 模拟共享池
POOL_SIZE=4 uvicorn app:app --port 8000 --workers 1 &

# 先打一批"慢"请求占住池,再打"快"请求看它被拒
python drive.py --url 'http://127.0.0.1:8000/slow?ms=2000' --steps 8 --seconds 3 &
sleep 0.3
python drive.py --url 'http://127.0.0.1:8000/slow?ms=10' --steps 50 --seconds 2
curl -s http://127.0.0.1:8000/stats
```

## 你会看到什么

离线(A),同一组负载、同一 seed:

```
SHARED    fast: rejected=427   p99_wait=25   ← 快请求被慢请求拖死,大量被拒、等待高
ISOLATED  fast: rejected=0     p99_wait=0    ← 隔离后快路毫发无伤
          slow: rejected=151                  ← 慢负载只坑自己那份配额
```

真实(B):慢请求占满 `POOL_SIZE=4` 期间,快请求拿到一批 503(`rejected` 上升)——共享池下,慢的把快的饿死了。

## 为什么

共享池里,慢请求(占用 2000ms)长期霸占池槽,offered load 把 `c` 顶满(`05`/`06` 的 ρ→1),快请求(本来 10ms 秒过)排不进、被拒。隔离(给快/慢各自独立的池)后,慢负载再慢也只能占满**它自己那份**,快路的池完全不受影响——`rejected` 从 427 归零。**这就是舱壁:一个进水不沉全船。** 代价是慢负载的 reject 反而上升(它的配额变小了),这是隔离的正确权衡:**牺牲非关键路径,保住关键路径。**

> 收尾:`pkill -f "uvicorn app:app --port 8000"`
