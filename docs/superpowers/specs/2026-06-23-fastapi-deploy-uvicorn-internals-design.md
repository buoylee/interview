# 设计 · FastAPI 裸机生产部署 + uvicorn 内臟

> 日期:2026-06-23
> 目标产物:重写 `fastapi-ops/01-foundation/README.md`(现为空 checklist 骨架)
> 形态:资深面试向的教学正文 + 可直接抄的生产配置 + 面试速记卡

---

## 1. 背景与动机

用户(Java/Go 转 Python,面试导向)对两件事仍不清楚:

1. **uvicorn 到底如何工作**——只知道 `uvicorn app:app` 能跑,不知内部发生什么。
2. **不用 Docker,如何在 Linux 上正经部署一个生产级 FastAPI 服务**。

### 仓库现状(已勘查)

| 主题 | 现状 | 位置 |
|---|---|---|
| worker 模型(WSGI/ASGI、gunicorn vs uvicorn、配几个) | ✅ 完整 | `python-concurrency/07-prod-web-workers/` |
| systemd 把程序变服务(自启/自愈/限资源/日志) | ✅ 完整,Python 那行就是 uvicorn | `linux-handson/08-systemd-and-services/` |
| FastAPI 生产化部署 | ⚠️ 仅空骨架(全 `[ ]` 无正文,偏 Docker) | `fastapi-ops/01-foundation/` |
| **uvicorn 内臟** | ❌ 缺(07 只讲 worker 模型,未拆 uvicorn 内部) | — |
| **不用 Docker 的端到端裸机部署走查** | ❌ 缺(零件散落,无主线串联) | — |

**缺口 = uvicorn 内臟 + 裸机端到端部署主线。** 本设计填这两个缺口。

### 为什么值得写(面试相关性,三层)

- **第一层(人人会,不加分)**:WSGI vs ASGI、为何多 worker(GIL)、worker 配几个。→ `07` 已覆盖。
- **第二层(资深分水岭,80% 候选人卡住)** ⭐:
  - uvicorn 单线程事件循环,路由里写阻塞调用会怎样?
  - 一个请求从 socket 到你的函数中间经过什么?(ASGI scope/receive/send)
  - 不用 Docker 怎么做开机自启 + 崩溃自愈?(systemd)
  - 为什么前面要放 nginx?uvicorn 不能直接对公网吗?
  - worker 数 × 连接池大小 = 对数据库的总连接数。
  - `--max-requests` / `--preload` / 优雅关闭。uvloop / httptools 为什么快。
- **第三层(架构师)**:从 QPS/P99 反推容量;裸机栈 ↔ K8s 对应关系(systemd ≈ 单机 K8s)。

本章主攻第二层(面试官区分「用过」和「懂生产」的标尺),并触及第三层。

---

## 2. 已确认的决策

| 维度 | 决策 |
|---|---|
| **放哪** | 填实 `fastapi-ops/01-foundation/README.md`(消灭空骨架,主题最对口) |
| **划界** | worker 数细节指向 `python-concurrency/07`;systemd 机制细节指向 `linux-handson/08`;asyncio 阻塞坑指向 `python-concurrency/05`。**不重写它们已讲透的部分。** |
| **深度/格式** | 教学正文(内臟写进正文)+ 完整可抄配置(systemd unit / nginx conf / gunicorn 命令,作参考不要求动手跑)+ 末尾面试速记卡(只做复习,不承载新知识)。与 `07`/`linux-handson/08` 同风格。 |
| **Docker** | 主体纯裸机;**结尾加一段裸机↔容器/K8s 对应表**(满足「不用 docker」又补上架构师考点)。 |
| **章节顺序** | **内臟先讲(Part A)、部署后讲(Part B)**——先懂单线程事件循环,后面多 worker / nginx 缓冲 / 重启才不是死记。 |

### 写作约定(沿用仓库既有 track 风格)

- 底层内幕写进正文教学(引入概念时就讲),问答题只是最后的复习自检层。
- 对标 Java/Go 做桥接(用户背景),但生态平衡、不绑死 Java。
- 完整可抄的配置块,带「为什么」注释。
- 「生产踩坑框 ⚠️」+「面试速记」+「小结 + 桥接指针」收尾。

---

## 3. 章节大纲

新标题:**`01 — FastAPI 生产化部署(裸机)+ uvicorn 内臟`**

### 开篇钩子
接此前对话:「改了代码没生效」的真因是**进程把模块持在内存里**——把「.pyc 缓存 / `--reload` / 部署时为何要重启」串起,引出「线上到底怎么把这进程正经跑起来」。

### Part A · uvicorn 到底如何工作(内臟,写进正文)
- **A1 ASGI 契约**:整个 app = 一个 `async def app(scope, receive, send)`;`FastAPI()` 对象就是它。对标:uvicorn≈Tomcat/Netty,FastAPI≈Controller,ASGI≈Servlet API。
- **A2 uvicorn 四零件**:事件循环(asyncio/**uvloop**=libuv)、HTTP 解析(**httptools**=C / h11 回退)、Server/Protocol 层、你的 app。`uvicorn[standard]` 带 uvloop+httptools。
- **A3 一个请求的完整生命**:socket 可读 → httptools 解析 → 建 scope → `await app(...)` → 路由 await I/O 时让出 → send 写回。全跑在单线程。
- **A4 资深分水岭题** ⭐:路由里写阻塞调用(`requests.get`/重 CPU)→ 卡死整个事件循环 → 此 worker 所有并发一起凉。指向 `python-concurrency/05-asyncio-pitfalls`。
- **A5 `--workers` 多进程**:主进程 bind socket → fork N 子进程共享 fd,内核分发新连接;主进程当监工(worker 死了补)。worker 数怎么定 → **指向 `07`,不重写**。gunicorn+UvicornWorker vs uvicorn --workers vs `fastapi run` 的历史与取舍。
- **A6 lifespan 协议**:uvicorn 用 `scope type=lifespan` 触发 startup/shutdown——建/关 DB 连接池的时刻,呼应开篇「进程持有状态」与 B3 的优雅关闭。

### Part B · 不用 Docker 在 Linux 正经部署(裸机四层)
总览图:`公网 → nginx → gunicorn+UvicornWorker → systemd 守护 → venv`。对标 Java(systemd 守 fat jar)/Go(守二进制);Python 多出「多 worker 层」因 GIL。
- **B1 venv**:依赖隔离,ExecStart 直指 venv 里的 gunicorn,不 `source activate`。
- **B2 进程管理器层**:启动命令 + worker 数起点(细节指 `07`)。
- **B3 systemd**(重点之一):完整可抄 `.service`(`ExecStart`/`Restart=on-failure`/`User`/`EnvironmentFile`/`MemoryMax`/`LimitNOFILE`/`TimeoutStopSec`);优雅关闭对接 A6 lifespan;机制细节 → **指向 `linux-handson/08`**。
- **B4 nginx 反代**:为什么 uvicorn 不能裸奔公网(慢客户端缓冲/slowloris、TLS 终止、静态、限流);unix socket 连法。
- **B5 零停机**:gunicorn `HUP` 滚动重启 / `systemctl reload`;`--reload` 仅开发。
- **B6 配置与密钥**:pydantic-settings + systemd `EnvironmentFile`,不硬编码。
- **B7 健康检查**:`/health/live`、`/health/ready`;裸机无 K8s,说清这俩给谁用(nginx upstream 探活 / 外部监控),且不要做重型操作。

### Part C · 生产踩坑框 ⚠️
阻塞事件循环、忘了 `daemon-reload`、`Type=simple` vs `forking`、`LimitNOFILE` 不够、**worker 数 × 连接池 = DB 总连接**、日志不配 logrotate。

### Part D · 面试速记卡(Q&A,只做复习自检)
按「人人会 / 资深分水岭 / 架构师」三层出题。

### Part E · 小结 + 裸机↔容器对应 + 桥接
一张表:裸机栈每层 ↔ Docker/K8s 对应物(venv≈镜像依赖层、systemd≈kubelet/Deployment、nginx≈Ingress、多 worker≈多 replica),点题「systemd ≈ 单机版 K8s」。桥接指针 → `07` / `linux-handson/08` / `python-concurrency/05` / `concurrency-capacity`。

---

## 4. 边界与约束

- **不重写**:WSGI/ASGI 基础对比、worker 数经验公式、systemd 机制全解、asyncio 坑——这些指向既有章节。
- **不碰**:Docker 多阶段构建、K8s 部署细节(交给 cloud-native / fastapi-ops 别处);Prometheus/OTel/日志采集(fastapi-ops 02-09)。
- **载体延续**:fastapi-ops track README 声称「各阶段围绕同一 FastAPI 项目演进」,本章给出最小 app 骨架作为后续章节载体,但以教学为主、不要求用户动手跑。

## 5. 成功标准

- 读完能回答 §1「第二层」全部问题,尤其「单线程事件循环阻塞的后果」「请求生命周期」「不用 Docker 怎么守护」。
- 给出一套可直接抄改上线的 venv + systemd unit + nginx conf。
- 与 `07`、`linux-handson/08` 无内容重复,只有指针。
- 篇幅 ~350-450 行,量级与既有 track 一致。
