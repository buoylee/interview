# 实验 e02 · 并发模型对比 —— event-loop 用一个线程扛住多少 I/O 并发

> 对应章节 [02 三种并发模型](../../02-concurrency-models/)。证明:I/O 密集场景下,单线程 event-loop 能扛住 thread-per-request 要几百线程才扛得住的并发。

## 目的

让你**亲手感受**承载单位的成本差异(`02 §2`):一个 uvicorn 进程 = 一个事件循环 = 一个线程,却能同时扛住上千个「在等 I/O」的请求。如果用阻塞线程模型,这需要上千个 OS 线程(上 GB 栈内存)。

## 跑什么

```bash
cd concurrency-capacity/lab/service

# async 模型:一个事件循环,POOL_SIZE 开大,看它扛并发
POOL_SIZE=2000 MODEL=async uvicorn app:app --port 8000 --workers 1 &

# 逐级加压,每个 /slow 请求"等" 50ms(模拟 I/O)
python drive.py --url 'http://127.0.0.1:8000/slow?ms=50' --steps 100,500,1000,2000 --seconds 5

# 看高水位在途数:一个线程同时扛了多少
curl -s http://127.0.0.1:8000/stats
```

## 你会看到什么

- `qps` 一路跟到接近目标 RPS,`p99` 维持在 ~50–80ms(没有排队恶化)。
- `/stats` 的 `max_in_flight` 冲到几百上千——**这就是 `L=λW`**(1000 RPS × 0.05s = 50,但突发瞬时更高),全部由**一个事件循环、一个线程**承载。

## 为什么

I/O 等待时,event-loop 把协程挂起、去推进别的协程,一个线程就轮转上千个「在途但在等」的请求(`02 §2` 的协程帧 ~KB 成本)。换成 thread-per-request,同样的 `max_in_flight` 意味着同样多的阻塞 OS 线程,内存和上下文切换会先于 CPU 把你压垮——这正是 C10k 问题的由来,也是为什么 I/O 密集服务要选 event-loop/goroutine。

> 收尾:`pkill -f "uvicorn app:app --port 8000"`
