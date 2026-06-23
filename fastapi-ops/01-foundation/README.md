# 01 — FastAPI 生产化部署(裸机)+ uvicorn 内脏

> 核心问题:一个「能跑」的 `uvicorn app:app` 和一个「能上生产」的 FastAPI,差在哪?
> 本章不用 Docker,讲清楚两件事:**uvicorn 内部到底怎么工作**,以及**怎么在一台 Linux 上把它跑成开机自启、崩溃自愈、能优雅关机的正经服务**。
> 这是后续所有章节(监控、追踪、压测、调优)共用的载体项目。

---

## 开篇 · 一个你大概率踩过的盲点

你改了一行代码,刷新页面——没生效。重启服务,生效了。为什么?

很多人以为是「`.pyc` 缓存旧了」。**不是。** Python 的 `.pyc`(`__pycache__/` 里的字节码缓存)靠源文件的 mtime+size 自动失效,你一改它就重编,基本不会 stale。

真正的原因是:**一个正在跑的 Python 进程,把所有 import 过的模块以对象形式持在内存里(`sys.modules`),它不会因为你改了硬盘上的 `.py` 就重新加载。** 就跟一个正在跑的 JVM 不会自动换掉已加载的 `.class` 一样——要么重启进程,要么有热重载机制(`uvicorn --reload` / Spring DevTools / JRebel)。

这件小事其实是整章的引子:**线上服务 = 一个长期驻留、持有状态(连接池、缓存)的进程。** 你怎么把它启动、守护、优雅关闭、改了代码怎么不中断地换掉——这就是「部署」。在讲怎么部署之前,得先看清这个进程内部长什么样:**uvicorn 到底在干什么。**

---

## Part A · uvicorn 到底如何工作

### A1 一句话定位:uvicorn 是个「翻译官」

> **uvicorn 是一个 ASGI 服务器。它的工作就是:在 socket 上讲 HTTP,把 HTTP 翻译成对你 app 的函数调用。**

对标 Java,一秒就懂:

| Python | Java 对应 | 干什么 |
|---|---|---|
| **uvicorn** | Tomcat / Netty | 处理 socket、解析 HTTP 协议的那层 |
| **FastAPI**(你写的) | Servlet / Controller | 业务逻辑 |
| **ASGI** | Servlet API | 上面两者之间的「接口契约」 |

Java 里 Tomcat 和你的 Controller 之间靠 Servlet API 解耦;Python 里 uvicorn 和你的 FastAPI 之间靠 **ASGI** 解耦。搞懂 ASGI,就搞懂了 uvicorn 和 FastAPI 的分工。

### A2 ASGI 契约:你的整个 app 其实是一个函数

这是最反直觉、但点破就通的事。你的 FastAPI app,在 uvicorn 眼里就是**一个 async 函数**,签名固定:

```python
async def app(scope, receive, send):
    ...
```

- `scope`:一个 dict,描述这次连接是什么——`type`(`http` / `websocket` / `lifespan`)、method、path、headers……≈ Java 的 `HttpServletRequest` 元数据。
- `receive`:一个 async 函数,`await receive()` 拿到下一个事件(比如请求 body 的一块)。
- `send`:一个 async 函数,`await send({...})` 把响应写回去(先发 `http.response.start` 带状态码+headers,再发 `http.response.body`)。

`FastAPI()` 这个对象本身**就是**这个 callable(底层是 Starlette 实现的)。uvicorn 启动时把它 import 进来、捏在手里,每来一个请求就 `await app(scope, receive, send)` 调一次。**你写的 `@app.get(...)` 路由,只是这个大函数内部的一次分发。**

> 心智模型:你不是在「写接口给 uvicorn 调」,你是把**整个应用打包成了一个异步函数**交给 uvicorn。这就是 ASGI 的全部。

### A3 uvicorn 内部的四个零件

```
       ┌──────────────────── 一个 uvicorn worker 进程 ──────────────────┐
socket │  ① 事件循环 (asyncio / uvloop)   ← 整个进程的心脏,单线程       │
─────▶ │  ② HTTP 解析器 (httptools / h11) ← 把 socket 字节流→请求对象    │
       │  ③ Server/Protocol:accept 连接、建 scope、调你的 app          │
       │  ④ 你的 ASGI app (FastAPI):async def app(scope, receive, send)│
       └────────────────────────────────────────────────────────────────┘
```

1. **事件循环**:`pip install "uvicorn[standard]"` 会带上 **uvloop**(基于 libuv——跟 Node.js 同一个底层 C 库,比标准 `asyncio` 事件循环快不少),装了默认就用它。这就是「每个 worker 内部一个事件循环」的那个循环。
2. **HTTP 解析器**:`[standard]` 还带 **httptools**(C 写的高速 HTTP 解析器),没装就退化到纯 Python 的 **h11**。负责把 socket 进来的原始字节 `GET /x HTTP/1.1\r\n...` 解析成结构化请求。
3. **Server/Protocol 层**:bind 一个 socket、跑 accept 循环;每个连接建一个 protocol 实例,解析完组出 `scope` dict,然后 `await app(...)`。
4. **你的 app**:跑业务,期间 `await` 任何 I/O(查 DB、调外部 API)时,事件循环就转去服务别的连接。

> 所以 `uvicorn[standard]` 不是可有可无——它把「纯 Python 的慢解析 + 慢循环」换成「C 的快解析 + libuv 的快循环」。生产一律装 `[standard]`。

### A4 一个请求在一个 worker 里的完整生命

```
socket 可读 → 事件循环醒 → httptools 解析字节 → 组出 scope
   → await app(scope, receive, send)   ← 进你的 FastAPI 路由
       → 路由里 await db.query(...)     ← 让出!循环转去服务别的请求
       ← DB 回来,循环把控制权调度回这里继续
   → 你 return 响应 → uvicorn 用 send() 把字节写回 socket
```

关键记忆点:**这一切跑在单线程上。** 一个 worker 进程 = 一个事件循环 = 一条线程,靠「谁 await 了就让出」实现并发,而不是靠多线程。这就是为什么单个 worker 能同时扛上千个连接:大家大部分时间都在等 I/O,轮流用这条线程的那一小段 CPU。

### A5 资深分水岭题 ⭐:在路由里写阻塞调用会怎样?

> **面试高频,80% 的人栽在这。**

既然整个 worker 就一条线程、靠 `await` 让出,那如果你在 `async def` 路由里写了一个**不让出**的调用——比如 `requests.get(...)`(同步 HTTP 库)、`time.sleep(5)`、或一段纯 CPU 的重计算——会发生什么?

**事件循环被这一个请求卡死。** 在它返回之前,这条线程没法去服务任何其他连接。这个 worker 上所有并发请求**一起冻住**。你压测会看到:QPS 上不去、P99 爆炸,但 CPU 还没满——因为大家在排队等那条被占住的线程。

正确做法:
- 异步 I/O 用异步库:`httpx`(替 `requests`)、`asyncpg`/SQLAlchemy async(替同步驱动)、`redis.asyncio`。
- 实在要调同步阻塞代码:`await run_in_threadpool(fn, ...)`(Starlette 提供)丢到线程池,别堵循环。
- 重 CPU 计算:丢进程池 / 任务队列(Celery,见 `python-concurrency/08`),别在请求线程里算。

> 这是 FastAPI 最大的坑,详见 [`python-concurrency/05-asyncio-pitfalls`](../../python-concurrency/05-asyncio-pitfalls/)。能讲清这题,面试官就知道你真懂事件循环,而不是只会调 API。

### A6 `--workers N`:用多进程绕开 GIL

单个 uvicorn worker 就一条线程,受 **GIL** 限制吃不满多核。所以线上要起多个 worker:

```
uvicorn app:app --workers 4
   主进程:bind 一个监听 socket → fork 4 个子进程(继承同一个 socket fd)
   ├── worker 1(自己一个事件循环)┐
   ├── worker 2                    ├ 4 个都 accept 同一个 socket,
   ├── worker 3                    │ 内核在它们之间分发新连接
   └── worker 4 ┘                  ┘
   主进程:只当监工,worker 死了重新 fork 一个,自己不处理请求
```

- **worker 数 ≈ 进程数** → 解决「吃多核」。
- **每个 worker 内部的事件循环** → 解决「单 worker 内的高并发」。
- **worker 配几个**:FastAPI 这种异步服务,worker 数 ≈ **CPU 核数**(不用同步框架那个 `2×核数+1`,因为单个事件循环已经能高并发,worker 多了只为吃满多核)。**前提是代码真 async 到底、不阻塞循环(A5)。** 详细的数字题(同步 vs 异步、gthread/gevent)见 [`python-concurrency/07-prod-web-workers`](../../python-concurrency/07-prod-web-workers/),本章不重复。

**三种起法,生产怎么选:**

```bash
# ① uvicorn 自己起多 worker —— 最简单
uvicorn app:app --workers 4 --host 0.0.0.0 --port 8000

# ② gunicorn 当监工 + UvicornWorker 干活 —— 老牌生产组合
gunicorn app:app -k uvicorn.workers.UvicornWorker -w 4 --bind 0.0.0.0:8000
#   gunicorn 的进程管理更成熟:优雅滚动重启(HUP)、--max-requests 防内存泄漏、
#   --preload 省内存。生产想要这些就用它。

# ③ FastAPI 官方 CLI —— 其实就是包了一层 uvicorn --workers
fastapi run app.py --workers 4
```

> 历史背景(面试会问):早年 uvicorn 自己的多进程管理较弱,大家用 **gunicorn + UvicornWorker**。现在 uvicorn 的 `--workers` 和 `fastapi run` 已经够用,但 gunicorn 那套生产参数(见下)仍然更全。两条路都对。

### A7 lifespan 协议:startup/shutdown 是怎么触发的

uvicorn 启动时,会先用一个 `scope["type"] == "lifespan"` 调你的 app:发 `lifespan.startup` 事件、等你回 `startup.complete`——**这一刻就是你的 FastAPI `lifespan` / `@app.on_event("startup")` 被执行的时刻**,建数据库连接池、预热缓存都在这。关机时发 `lifespan.shutdown`,你在这里优雅关闭连接池。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()   # 启动:建连接池(uvicorn 发 lifespan.startup 时跑到这)
    yield                                  # ← 服务运行期
    await app.state.pool.close()           # 关机:优雅关池(收到 SIGTERM 时跑到这)

app = FastAPI(lifespan=lifespan)
```

记住这个 `yield` 上下两半:**上半在进程启动时跑一次,下半在进程优雅关闭时跑一次。** 这正好对接 Part B 的 systemd——`systemctl stop` 发 SIGTERM,你的 `yield` 下半就有机会排空连接、关池,而不是被硬杀。

---

## Part B · 不用 Docker,在 Linux 上正经部署

「正经生产级」= 下面这四层,缺一层都算不上正经:

```
公网 ──▶ ① nginx (443/TLS、静态文件、限流、缓冲慢客户端)
            │  反代到本机
            ▼  unix socket 或 127.0.0.1:8000
         ② gunicorn master + 4×UvicornWorker   ← 真正跑你的代码(Part A)
            ▲
         ③ systemd 守着它(开机自启 / 崩溃自愈 / SIGTERM 优雅关 / cgroup 限资源 / 日志进 journald)
         ④ venv 隔离依赖(绝不用系统 python)
```

对标你熟的栈,骨架完全一样:

| | Java | Go | Python(本章) |
|---|---|---|---|
| 跑代码 | Spring Boot fat jar | 单个二进制 | gunicorn + N×UvicornWorker |
| 守护 | systemd | systemd | systemd |
| 入口 | nginx | nginx | nginx |

唯一的区别:Python 因 GIL 多出 ②那层**多 worker**(Java/Go 单进程就吃满多核,不需要)。这是 GIL 给部署架构带来的最直接差异。

### B1 venv:依赖隔离

```bash
python3 -m venv /opt/myapp/venv
/opt/myapp/venv/bin/pip install "uvicorn[standard]" gunicorn fastapi
```

绝不用系统 Python 装依赖(会污染系统、版本打架)。后面 systemd 的 `ExecStart` 直接指 venv 里的可执行文件,**不需要 `source activate`**——指对路径就行。

### B2 进程管理器层

就是 A6 那套。命令二选一(gunicorn 生产参数更全,推荐):

```bash
/opt/myapp/venv/bin/gunicorn app:app \
    -k uvicorn.workers.UvicornWorker \
    -w 4 \
    --bind unix:/run/myapp/gunicorn.sock \
    --timeout 30 \
    --max-requests 2000 --max-requests-jitter 200 \
    --graceful-timeout 30
```

几个一定要懂的生产参数:

- `--timeout 30`:一个 worker 处理单个请求超过 30s,master 杀掉重启它。慢接口/重活要调大,否则 worker 被反复杀。
- `--max-requests 2000` + `--max-requests-jitter`:每个 worker 处理 2000 个请求后自动重启——**缓解内存泄漏**(Python 长跑进程内存只增不减时定期回收)。jitter 加随机,避免所有 worker 同时重启造成抖动。
- `--preload`:master 先 import 应用再 fork worker,省内存(写时复制共享)、加快启动;代价是改代码要重启 master,且 fork 后某些资源(DB 连接、随机种子)要在 worker 里重建。
- `--graceful-timeout 30`:收到停止信号后,给 worker 30s 排空在途请求再杀。

### B3 systemd:把它变成一个正经服务(本章重点)

**这才是「不用 Docker 但要正经」的灵魂。** 没有 Docker,靠谁做开机自启、崩溃自愈、优雅关机、限资源、收日志?答案是 systemd——现代 Linux 的 PID 1。

`/etc/systemd/system/myapp.service`:

```ini
[Unit]
Description=My FastAPI App
After=network.target                 # 网络就绪后再启动
Requires=postgresql.service          # 强依赖(可选)

[Service]
User=appuser                         # 非 root 跑(最小权限)
Group=appuser
WorkingDirectory=/opt/myapp
RuntimeDirectory=myapp               # 自动建 /run/myapp(放 unix socket)
EnvironmentFile=/etc/myapp/env       # 密钥/配置从这读,绝不硬编码进代码
ExecStart=/opt/myapp/venv/bin/gunicorn app:app \
          -k uvicorn.workers.UvicornWorker -w 4 \
          --bind unix:/run/myapp/gunicorn.sock \
          --timeout 30 --max-requests 2000 --max-requests-jitter 200

Restart=on-failure                   # 崩了自动拉起 —— 这就是「生产怎么守护」的答案
RestartSec=3
TimeoutStopSec=30                    # 停止宽限期:先 SIGTERM,30s 不退再 SIGKILL
MemoryMax=1G                         # cgroup 内存上限,超了 OOMKilled
LimitNOFILE=65536                    # fd 上限,高并发(大量连接)必调大

[Install]
WantedBy=multi-user.target           # enable 时挂到这,决定开机自启
```

上线三条命令:

```bash
sudo systemctl daemon-reload         # 改了 .service 必须 reload(90% 的「不生效」是忘了这步)
sudo systemctl enable --now myapp    # 既设开机自启,又立即启动
journalctl -u myapp -f               # 看日志(stdout/stderr 自动进 journald,你不用做日志重定向)
```

这套下来你白嫖了 Docker/K8s 帮你做的大半事情:**开机自启 ✅、崩溃自愈(`Restart`)✅、优雅关机(SIGTERM → 触发 A7 的 lifespan 关池)✅、资源限制(cgroup)✅、统一日志(journald)✅。**

> systemd 的机制细节(`enable` vs `start`、`Type=simple` vs `forking`、cgroup、journald vs 文件日志、timer 替代 cron)在 [`linux-handson/08-systemd-and-services`](../../linux-handson/08-systemd-and-services/) 讲透了,本章不重复——那一章的「四语言桥接表」里 Python 那行就是这里的 uvicorn。

### B4 nginx 反代:为什么 uvicorn 不该裸奔公网

uvicorn 技术上能 `--host 0.0.0.0` 直接对公网,但生产不该这么干。前面必须有一层 nginx(或 Caddy/其他反代),原因:

1. **缓冲慢客户端(最重要的技术理由)**:回顾 A4——uvicorn 是单线程事件循环。一个**慢连接**(慢慢发请求 / 慢慢收响应,典型攻击叫 slowloris)如果直连 uvicorn,会占住一个协程、拖慢整个循环。nginx 先把整个请求**完整收齐**再一次性喂给 uvicorn,把慢客户端挡在外面。
2. **TLS 终止**:HTTPS 证书在 nginx 卸载,uvicorn 只跑明文 HTTP(本机回环,安全)。
3. **静态资源**:JS/CSS/图片交给 nginx 发,别浪费 Python 进程。
4. **限流 / 路由 / 多服务**:`limit_req`、按 path 分流到不同后端。

`/etc/nginx/conf.d/myapp.conf`:

```nginx
upstream myapp {
    server unix:/run/myapp/gunicorn.sock;   # 本机走 unix socket,免走 TCP 栈,最快
}

server {
    listen 443 ssl;
    server_name myapp.example.com;
    # ssl_certificate ... (certbot 拿 Let's Encrypt 证书)

    location / {
        proxy_pass http://myapp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;   # 让 app 知道原始是 https
    }

    location /static/ { alias /opt/myapp/static/; }   # 静态交给 nginx
}
```

> 配套:让 uvicorn/gunicorn 信任 nginx 转发的真实 IP,要加 `--proxy-headers --forwarded-allow-ips='*'`(或具体 nginx IP),否则 `request.client.host` 拿到的是 nginx 的回环地址而不是真实客户端 IP。WebSocket 还需 nginx 转发 `Upgrade`/`Connection` 头。

### B5 零停机:改了代码怎么不中断地换掉

回到开篇——进程持有内存中的旧代码,要换就得重启。但生产不能「停了再起」造成中断。做法:

- **gunicorn 滚动重启**:`kill -HUP <master_pid>`(或 `systemctl reload myapp`,见下)让 gunicorn **逐个**用新代码替换 worker,旧 worker 处理完手头请求再退——服务不断。
- 在 unit 里加一行就能 `systemctl reload`:`ExecReload=/bin/kill -s HUP $MAINPID`。
- `uvicorn --reload` **只配开发用**(它是文件监听热重载,有性能开销、不适合生产)。

### B6 配置与密钥:别硬编码

用 `pydantic-settings` 从环境变量/`.env` 读配置,密钥(DB 密码、API key)走 systemd 的 `EnvironmentFile=/etc/myapp/env`(文件权限设 `600`、属主 `appuser`):

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    log_level: str = "INFO"
    class Config:
        env_file = ".env"   # 本地开发读 .env;生产由 systemd EnvironmentFile 注入

settings = Settings()       # 启动时校验:少了必填项直接报错,不让你带病上线
```

> 好处:配置集中、类型校验、缺失即报错;密钥不进 git、不进镜像、不进代码。

### B7 健康检查:裸机上谁来探活?

```python
@app.get("/health/live")    # liveness:进程还活着吗?(只回 200,不查依赖)
async def live(): return {"status": "ok"}

@app.get("/health/ready")   # readiness:依赖就绪吗?(轻量 ping 一下 DB/Redis)
async def ready():
    await app.state.pool.execute("SELECT 1")
    return {"status": "ready"}
```

两个原则:**liveness 绝不查业务依赖**(否则 DB 抖一下你的进程就被误判杀掉);**健康检查不做重型操作**(别 `SELECT count(*)` 整张表)。

裸机没有 K8s,这俩给谁用?诚实地说:
- **外部监控/Uptime 探测**(Prometheus blackbox exporter、Uptime Kuma 等)定时打 `/health/ready`,挂了告警。
- **nginx upstream**:开源版 nginx 只做**被动**健康检查(某 upstream 连续失败 N 次就暂时摘掉),**主动**定时探测要 nginx Plus 或第三方模块。所以裸机下「探活+告警」主要靠外部监控,不像 K8s 有 kubelet 自动重启。这也正是 Part E 要讲的「systemd ≈ 单机 K8s,但探活这块弱一些」。

---

## Part C · 生产踩坑框 ⚠️

> **在路由里写了阻塞调用** → 卡死整个事件循环,这 worker 所有并发一起凉(A5)。FastAPI 头号坑。

> **改了 `.service` 不生效** → 90% 是忘了 `sudo systemctl daemon-reload`。改完 unit 必须 reload 再 restart。

> **`Type` 用错** → 现代程序保持**前台运行**(systemd 默认 `Type=simple`),别给 gunicorn 加 `--daemon`。程序自己 daemonize 会让 systemd 误判主进程退出 = 失败。

> **`LimitNOFILE` 默认不够** → 高并发 = 大量连接 = 大量 fd,不调大就 `Too many open files`。

> **worker 数 × 连接池大小 = 对数据库的总连接数** → 4 worker × pool 10 = 40 条连接,再 × 机器数。配不好直接打满 DB 连接上限,经典生产事故。

> **日志写文件不配 logrotate** → 直接写 `/var/log/app.log` 又不切割,迟早写满磁盘。要么交给 journald,要么配 logrotate。

> **FastAPI 配成同步 worker** → 异步应用必须用 ASGI/uvicorn worker,错配成普通同步 WSGI worker 会让异步代码退化甚至报错。

---

## Part D · 面试速记卡(只做复习自检)

**人人会的(不加分)**

- WSGI vs ASGI?→ WSGI 同步(一请求占一 worker/线程到完成,Flask/Django+gunicorn);ASGI 异步(基于事件循环,一 worker 并发海量请求,支持 WebSocket,FastAPI+uvicorn)。
- 为什么 Python 要多 worker,Java 不用?→ 单 Python 进程受 GIL 吃不满多核,多进程才能利用多核+故障隔离;Java 单进程多线程即可。

**资深分水岭** ⭐

- uvicorn 是什么?→ ASGI 服务器,在 socket 上讲 HTTP,把它翻成 `await app(scope, receive, send)` 调你的 FastAPI,跑在单线程事件循环上。
- 一个请求从 socket 到你的函数经过什么?→ socket 可读 → httptools 解析 → 建 scope → `await app(...)` → 路由 await I/O 让出 → send 写回。
- 路由里写 `requests.get()` 会怎样?→ 阻塞调用卡死单线程事件循环,这 worker 所有并发请求一起冻住;改用 `httpx` 异步库或丢线程池。
- 不用 Docker 怎么做开机自启+崩溃自愈?→ 写 systemd `.service`(`Restart=on-failure` + `enable --now`)。
- 为什么前面要放 nginx?→ 缓冲慢客户端(防 slowloris 占住事件循环)、TLS 终止、发静态、限流。
- `--max-requests` 干嘛?→ worker 处理 N 个请求后自动重启,缓解内存泄漏;配 jitter 避免同时重启。
- uvloop / httptools 为什么快?→ uvloop 基于 libuv(C),httptools 是 C 写的 HTTP 解析,替掉纯 Python 的慢实现。
- 优雅关机怎么做?→ systemd `stop` 发 SIGTERM → uvicorn 触发 lifespan 的 shutdown 段排空/关池 → `TimeoutStopSec` 内不退才 SIGKILL。

**架构师**

- worker 数 × 连接池 = DB 总连接数,怎么避免打满?→ 算总量、压测定、必要时上连接池中间件(pgbouncer)。
- 这套裸机栈和 K8s 什么关系?→ 见 Part E,systemd ≈ 单机版 K8s。

---

## Part E · 小结 + 裸机 ↔ 容器对应

**一句话记忆点**

> uvicorn = ASGI 服务器,在 socket 上讲 HTTP、翻成 `await app(scope,receive,send)` 调你的 FastAPI,跑在单线程事件循环上,`--workers` 靠多进程绕 GIL。
> 裸机正经部署 = **venv(隔离)→ gunicorn+UvicornWorker(跑代码绕 GIL)→ systemd(自启/自愈/优雅关/限资源/日志,替代 Docker)→ nginx(TLS/缓冲/静态)**。

**裸机 ↔ Docker/K8s 对应**(你说不用 Docker,但这个对应是架构师考点)

| 裸机这一层 | Docker/K8s 对应物 | 干的事 |
|---|---|---|
| venv | 镜像里打包的依赖层 | 依赖隔离 |
| systemd `.service` | kubelet + Deployment | 拉起、守护、重启、限资源 |
| `Restart=on-failure` | `restartPolicy` / ReplicaSet 补 Pod | 崩溃自愈 |
| `MemoryMax` / `LimitNOFILE` | Pod `resources.limits` / cgroup | 资源限制 |
| 多 worker 进程 | 多 replica Pod | 绕 GIL 吃多核 + 容量 |
| nginx 反代 | Ingress / Service | 入口、TLS、路由 |
| `/health/ready` + 外部监控 | readinessProbe(kubelet 主动探) | 探活 |
| `systemctl reload`(HUP 滚动) | 滚动更新(rolling update) | 零停机部署 |

> 点题:**systemd 在很多方面就是「单机版的 K8s」**——拉起、守护、健康、限资源、滚动。理解了这套裸机栈,K8s 的 Pod 生命周期会非常好懂。区别主要在:K8s 是**分布式**调度 + **主动**健康探测 + 自动扩缩,裸机这些要靠外部监控和人工补。

**桥接指针**

- worker 模型、worker 数怎么定、WSGI/ASGI 完整对比 → [`python-concurrency/07-prod-web-workers`](../../python-concurrency/07-prod-web-workers/)
- 别在事件循环里阻塞(A5 的坑) → [`python-concurrency/05-asyncio-pitfalls`](../../python-concurrency/05-asyncio-pitfalls/)
- systemd 机制全解 / journald / cgroup → [`linux-handson/08-systemd-and-services`](../../linux-handson/08-systemd-and-services/)
- 从 QPS/P99 反推 worker 数与单机容量 → [`concurrency-capacity`](../../concurrency-capacity/)

---

## 参考

- [Uvicorn Deployment](https://www.uvicorn.org/deployment/)
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [ASGI 规范](https://asgi.readthedocs.io/)
- [Gunicorn Settings](https://docs.gunicorn.org/en/stable/settings.html)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

➡️ 下一章:[`02-system-metrics`](../02-system-metrics/) — 服务慢/挂,第一时间看什么系统指标。
