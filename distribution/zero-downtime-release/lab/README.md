# Lab — 亲眼看到「丢请求 → 优雅排空 → 不丢了」

配套 [`03 优雅下线`](../03-graceful-shutdown.md)。本机 docker(OrbStack/Docker Desktop 都行)即可跑,**不需要 k8s**。

## 这个 lab 能演示什么 / 不能演示什么(诚实边界)

| 能真实复现 ✅ | 需要真 k8s,这里只讲机制 ❌ |
|---|---|
| **非优雅 vs 优雅停机**对在途请求的差别(SIGKILL 掐断 vs SIGTERM 排空) | k8s **endpoint 传播竞态**(链路 A vs 链路 B) |
| **grace 宽限期**的价值(`stop_grace_period` 给在途留时间) | **`preStop` sleep** 推迟 SIGTERM 的效果 |
| **keep-alive** 复用连接在后端消失时被 reset(ch05 的伏笔) | readiness 探针驱动的**主动摘流量**(nginx OSS 不探 readiness) |
| nginx **被动重试**(`proxy_next_upstream`)如何兜住新连接 | PodDisruptionBudget / 滚动时序 |

> 为什么 compose 演不了 preStop/endpoint 竞态?因为那条竞态是 **k8s 控制面异步传播**造成的;compose 里 nginx 用的是**静态 upstream + 被动健康检查**,没有"Endpoints 广播"这条链路。想真跑 k8s 那条,见 [`kind-appendix.md`](./kind-appendix.md)(可选)。
>
> **但核心教训这里全在**:停机方式不对就掉在途请求;给足 grace + 让进程优雅排空,就不掉。preStop 那层是"把优雅排空挪到对的时刻",机制在正文讲透了。

---

## 起步

```bash
cd distribution/zero-downtime-release/lab
docker compose up -d --build
curl -s http://localhost:8080/work        # {"instance":"app1"...} 或 app2,说明 LB 通了
```

---

## 场景 A:优雅停机(`docker stop`,SIGTERM + 宽限)→ 不丢

**终端 1** 起压测(并发 12,持续 30s):

```bash
bash load.sh 30
```

**终端 2**(压测跑着时)优雅停掉一个后端:

```bash
docker compose stop -t 30 app1
#   docker 发 SIGTERM → uvicorn 停 accept、排空在途的 /work、再退;
#   30s 宽限足够 2s 的在途请求跑完。新连接被 nginx 改打 app2。
```

回终端 1 看汇总,**掉请求合计 ≈ 0**(偶尔 1~2 个是 keep-alive 复用连接的 reset,正是 ch05 的现象)。
`docker compose logs app1` 能看到 `shutdown: in-flight drained` —— 优雅关跑到了。

---

## 场景 B:非优雅停机(`docker kill -s SIGKILL`,立即)→ 丢

先恢复:

```bash
docker compose up -d app1
```

**终端 1** 重新起压测:

```bash
bash load.sh 30
```

**终端 2**(压测跑着时)硬杀一个后端:

```bash
docker compose kill -s SIGKILL app1
#   立即终止,SIGKILL 不可捕获 → 此刻正在 app1 上跑的 /work 全部被掐断。
```

回终端 1 看汇总,**掉请求合计明显 > 0**(那一批正在 app1 在途的请求拿到 connection reset / 502)。
`docker compose logs app1` 看不到 `shutdown` 那行 —— 进程没机会优雅关。

---

## 对照结论

| | 停机方式 | 在途请求 | 掉请求 | logs 有 shutdown? |
|---|---|---|---|---|
| 场景 A | `stop -t 30`(SIGTERM+宽限) | **排空完成** | ≈0 | ✅ |
| 场景 B | `kill -s SIGKILL`(立即) | **被掐断** | >0 | ❌ |

这就是 ch03 的地基:**优雅关 = 给进程"停 accept → 排空在途 → 再退"的机会**。
在真 k8s 里,光有这个还不够——还要 `preStop` 把"开始优雅关"的时刻**推迟到流量摘干净之后**,否则关早了照样掉(那一层去 [`kind-appendix.md`](./kind-appendix.md) 真跑)。

---

## 加演:看 readiness-first 这一招(为什么 compose 里它"不够")

```bash
curl -X POST http://localhost:8080/admin/drain   # 把某个副本 readiness 翻 503
curl -s http://localhost:8080/health/ready        # 多打几次,有时 503(命中 draining 的那台)
```

你会发现:**即便 readiness 翻了 503,nginx OSS 还是照样往这台转流量** —— 因为它根本不探 `/health/ready`。
这正是 ch03 C3 的点:**readiness-fail 需要一个"消费它"的角色**(k8s Endpoints / Ingress / 云 LB)才有用;在裸 nginx OSS 下,你靠的是连接排空 + 被动重试,不是 readiness。换到 k8s,readiness 才真正驱动摘流量。

---

## 清理

```bash
docker compose down
```

> 跑脚本务必 `bash load.sh`(别在 zsh 下直接 `./load.sh` 或 `sh load.sh`):脚本用了 bash 的数组式变量与 `$(( ))`,zsh/sh 行为不一致。见仓库根的踩坑记录。
