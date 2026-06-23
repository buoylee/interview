# 实验 e05 · 池饿死 —— 池大小逼近负载时,等待如何指数爆炸

> 对应章节 [05 池定容](../../05-pools/)。证明:池是 M/M/c 队列,`c` 逼近 offered load 时等待爆炸;留一点余量,等待几乎归零。

## 目的

验证池定容的主公式:大小 `c` 必须 `> offered load a=λS`,且**逼近 `a` 时等待是 `1/(1−ρ)` 式爆炸**——所以要留余量,不能卡着算。

## 跑什么

### A. 离线、确定性(纯排队论,秒出)

```bash
cd concurrency-capacity
python lab/sim/starve.py --lam 80 --service-time 0.1
# offered load a = 80 × 0.1 = 8 erlang,扫 c 从 9 到 20
```

### B. 真实服务(把池调到刚好等于负载)

```bash
cd concurrency-capacity/lab/service
# 池=8,占用 100ms → 池能力 80 RPS;打 80 RPS 就是 ρ≈1
POOL_SIZE=8 uvicorn app:app --port 8000 --workers 1 &
python drive.py --url 'http://127.0.0.1:8000/slow?ms=100' --steps 40,72,80 --seconds 5
```

## 你会看到什么

离线(A):

```
c=9  → 等待 65.3ms   ← c 只比 a=8 大 1,挤,等待巨大
c=10 → 等待 20.5ms
c=12 → 等待  3.5ms   ← 留了 50% 余量,顺畅
```

真实(B):RPS 从 40(ρ=0.5,P99 ~105ms)推到 72(ρ=0.9),P99 明显抬头;到 80(ρ≈1)开始排队/拒绝。

## 为什么

`c=9` 对 `a=8` 意味着利用率 ρ=8/9≈0.89,正处在 `1/(1−ρ)` 曲线的陡峭段;`c=12` 时 ρ=0.67,落在平缓段。**这就是为什么 `05` 说池大小要配到 offered load 之上 + 余量**:差一两个名额,等待差一个数量级。同时印证「别只看够不够,要看离饱和多近」。

> 收尾:`pkill -f "uvicorn app:app --port 8000"`
