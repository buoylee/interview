# 08 · systemd 与服务管理

> 🧪 **环境**:VM shell(`multipass shell linux-lab`),多数命令需 `sudo`
> 工程化第一站。`01`/`03` 你用 `nohup ... &` 起后台进程——但生产服务要**开机自启、崩溃自愈、统一日志、资源受限**,这正是 systemd 的活。它还把前面几章串起来:PID 1(`03`)、cgroup 限制(`04`)、fd 上限(`05`)、日志(`07`)。

---

## 一、开篇盲点

- 你 `nohup ./app &` 起服务——机器重启就没了、崩了不会拉起、日志还得自己管。生产服务不该这么跑。
- `systemctl start` 背后到底做了什么?为什么有的服务 `enable` 了能开机自启、有的不行?
- `journalctl` 的日志和 `/var/log` 里的文件日志是什么关系?
- systemd 怎么限制一个服务的 CPU/内存(和 `04` 的 cgroup 什么关系)?

---

## 二、正文 · 原理

### 2.1 systemd 是什么

systemd 是现代 Linux 的 **PID 1**(回顾 `03`:1 号进程是所有进程的祖先),既是**系统管理器**(管开机流程)也是**服务管理器**(拉起、守护、收日志、限资源)。它取代了老的 SysV init 脚本。

> 你日常打交道的 `systemctl`(控制服务)和 `journalctl`(看日志)就是它的两个前台命令。

### 2.2 一切皆 unit

systemd 把要管理的东西抽象成 **unit**,常见类型:

| 类型 | 管什么 |
|------|--------|
| `.service` | 一个服务/守护进程(最常用) |
| `.socket` | 套接字激活(按需拉起服务) |
| `.timer` | 定时任务(替代 cron) |
| `.target` | 一组 unit 的集合 / 运行级别(如 `multi-user.target` ≈ 多用户文本模式) |
| `.mount` | 挂载点(接 `02` 挂载) |

### 2.3 一个 `.service` 文件长什么样

```ini
[Unit]
Description=My App
After=network.target          # 依赖:网络就绪后再启动
Requires=postgresql.service   # 强依赖(它没起,我也别起)

[Service]
ExecStart=/usr/bin/java -jar /opt/app/app.jar   # 启动命令(前台运行)
Restart=on-failure            # 崩溃自动拉起
RestartSec=3
User=appuser                  # 以哪个用户跑(接 02 权限)
Environment=PROFILE=prod
MemoryMax=512M                # 内存上限(接 04 cgroup)
LimitNOFILE=65536             # fd 上限(接 05)
TimeoutStopSec=30             # 停止宽限期(接 03 SIGTERM→SIGKILL)

[Install]
WantedBy=multi-user.target    # enable 时挂到这个 target(决定开机自启)
```

三段:`[Unit]` 元信息和依赖、`[Service]` 怎么跑、`[Install]` 开机自启挂到哪。

### 2.4 systemctl 日常(`enable` vs `start` 是高频题)

| 命令 | 作用 |
|------|------|
| `systemctl start/stop/restart <svc>` | **立即**启停(本次,不影响开机) |
| `systemctl enable/disable <svc>` | 设/取消**开机自启**(本质:在 `multi-user.target.wants/` 建/删一个 symlink) |
| `systemctl enable --now <svc>` | 既开机自启又立即启动 |
| `systemctl status <svc>` | 看运行状态、主 PID、cgroup、最近几行日志 |
| `systemctl daemon-reload` | **改了 `.service` 文件后必须执行**,让 systemd 重新加载配置 |
| `systemctl cat/edit <svc>` | 看/改 unit 文件 |

> **`enable` vs `start` 的区别**:`start` 是「现在跑起来」,`enable` 是「以后开机时自动跑」。两者独立——可以 enable 了但没 start(下次开机才生效),也可以 start 了但没 enable(重启后不自启)。

### 2.5 自愈 + 优雅关闭(接 03 信号)

- **自愈**:`Restart=on-failure`(或 `always`)让进程异常退出时 systemd 自动拉起——这就是「生产怎么守护服务」的答案,不用自己写 while 循环或 supervisor。
- **优雅关闭**:`systemctl stop` 先给主进程发 **`SIGTERM`**(回顾 `03`),等 `TimeoutStopSec`(默认 90s)还没退,再发 **`SIGKILL`**。所以你的 app 捕获 SIGTERM 做收尾,systemd 会配合等待。

### 2.6 资源限制(接 04 cgroup / 05 fd)

systemd 给**每个 service 单独建一个 cgroup**,这些指令直接写进 cgroup:

| 指令 | 限制 | 对应章 |
|------|------|--------|
| `MemoryMax=512M` | 内存上限,超了 cgroup OOM(`OOMKilled`) | `04` |
| `CPUQuota=50%` | CPU 配额 | — |
| `LimitNOFILE=65536` | 打开文件/socket 上限 | `05`(`Too many open files`) |
| `TasksMax=4096` | 进程/线程数上限 | `03` |

> 这解释了 `04`「容器/服务 OOMKilled」和 `05`「fd 不够要调大」在 systemd 下怎么配。

### 2.7 journald:服务日志去哪了(接 07 监控先行)

服务的 **stdout/stderr 自动被 journald 收走**(回顾 `01`:服务往 fd 1/2 写,systemd 把这两个 fd 接到 journald)。所以你**不用自己做日志重定向**,`journalctl` 统一查:

```bash
journalctl -u myapp -f                 # 跟踪某服务日志(像 tail -f)
journalctl -u myapp --since "10 min ago"
journalctl -u myapp -p err             # 只看 error 及以上
journalctl -b                          # 本次开机以来
```

**journald vs 文件日志**:journald 结构化、带元数据、统一查询/按服务过滤;传统应用仍可能直接写 `/var/log/*.log` 文件,那就要配 **logrotate** 切割归档,否则磁盘写满(接 `05`:别 `rm` 在写的日志,logrotate 用 `copytruncate`)。

### 2.8 timer 替代 cron(简述)

`.timer` + `.service` 做定时任务,比 cron 多了:日志(journald)、依赖、资源限制、错过补跑(`Persistent=true`)。`systemctl list-timers` 看。

---

## 三、怎么看(命令 + 真实输出怎么读)

```console
$ systemctl status nginx
● nginx.service - A high performance web server
     Active: active (running) since ...; 2h ago      # ← 状态 + 起多久
   Main PID: 812 (nginx)                              # ← 主进程
     Memory: 12.3M  (max: 512.0M)                     # ← cgroup 内存(接 04)
     CGroup: /system.slice/nginx.service              # ← 它的 cgroup
             ├─812 nginx: master
             └─813 nginx: worker
     (最近几行日志直接显示在这)

$ systemctl --failed                 # 所有启动失败的服务(排查第一站)
$ systemctl list-units --type=service
$ systemctl show nginx -p Restart -p MemoryMax    # 看生效的某项配置
$ systemd-cgtop                       # 按 cgroup 看实时资源(像 top)
```

---

## 四、动手实验(沙箱)

> 🧪 在 `multipass shell linux-lab` 里跑,需要 `sudo`。

**实验 1:写一个自己的服务并跑起来**
```bash
sudo tee /etc/systemd/system/hello.service >/dev/null <<'EOF'
[Unit]
Description=Hello demo
After=network.target
[Service]
ExecStart=/bin/bash -c 'while true; do echo "hello $(date)"; sleep 3; done'
Restart=on-failure
MemoryMax=50M
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload          # 改了 unit 必须 reload
sudo systemctl start hello
systemctl status hello --no-pager | head -12
journalctl -u hello -n 5 --no-pager   # 看它的输出进了 journald
sudo systemctl enable hello           # 设开机自启(看它建了 symlink)
```

**实验 2:崩溃自愈(`Restart=on-failure`)**
```bash
MAINPID=$(systemctl show hello -p MainPID --value)
echo "主进程 $MAINPID,杀掉看 systemd 是否拉起新的"
sudo kill -9 "$MAINPID"; sleep 4
systemctl show hello -p MainPID --value   # 变成了新的 PID —— 被自动拉起
```

**实验 3:资源限制触发 cgroup OOM(接 04)**
```bash
sudo systemctl edit --full --force memhog.service >/dev/null 2>&1 <<'EOF' || true
EOF
sudo tee /etc/systemd/system/memhog.service >/dev/null <<'EOF'
[Service]
ExecStart=/usr/bin/stress-ng --vm 1 --vm-bytes 200M --vm-keep
MemoryMax=50M
EOF
sudo systemctl daemon-reload
sudo systemctl start memhog; sleep 5
systemctl status memhog --no-pager | grep -E 'Active|Memory|Main'  # 被 OOM,看状态
journalctl -u memhog -n 5 --no-pager | grep -i kill || true
```

**实验 4:清理**
```bash
sudo systemctl stop hello memhog 2>/dev/null
sudo systemctl disable hello 2>/dev/null
sudo rm -f /etc/systemd/system/hello.service /etc/systemd/system/memhog.service
sudo systemctl daemon-reload
```

---

## 五、生产踩坑框 ⚠️

> **改了 `.service` 不生效**:90% 是忘了 `sudo systemctl daemon-reload`。改完 unit 文件必须 reload,再 `restart`。

> **服务起不来怎么查**:`systemctl status <svc>`(看 Active 失败原因)→ `journalctl -u <svc> -n 50`(看最后报错)。常见:`ExecStart` 路径错、`User=` 没权限(接 `02`)、端口被占(接 `06` `ss -lntp`)、依赖没起。

> **`Type=simple` vs `Type=forking`**:现代程序应**前台运行**(`simple`,默认)。如果程序自己 daemonize(fork 到后台),systemd 会以为主进程退出了而误判失败——这种老程序要设 `Type=forking` + `PIDFile=`。

> **`LimitNOFILE` 默认可能不够**:高并发服务(大量连接=大量 fd,接 `05`)要显式调大,否则 `Too many open files`。

> **日志写文件不配 logrotate**:服务直接写 `/var/log/app.log` 又不切割,迟早写满磁盘(接 `05`)。要么交给 journald,要么配 logrotate。

---

## 六、本章面试速记

- **systemd 是什么?和 init 的关系?** 现代 Linux 的 PID 1,系统与服务管理器,取代 SysV init;管开机、拉起守护服务、收日志、限资源。
- **怎么把一个程序做成开机自启 + 崩溃自愈的服务?** 写 `.service`(`ExecStart` + `Restart=on-failure` + `[Install] WantedBy=multi-user.target`),`daemon-reload` 后 `enable --now`。
- **`enable` 和 `start` 区别?** `start` 立即启动(本次);`enable` 设开机自启(建 symlink),两者独立。
- **服务起不来怎么排查?** `systemctl status` + `journalctl -u <svc>`,看 ExecStart/权限/端口/依赖。
- **systemd 怎么限制服务资源?** 给每个 service 建 cgroup,用 `MemoryMax`/`CPUQuota`/`LimitNOFILE`/`TasksMax`。
- **`systemctl stop` 怎么停的?** 先 SIGTERM、等 `TimeoutStopSec` 再 SIGKILL(接 `03` 优雅关闭)。

---

## 七、小结 + 桥接 + 延伸

**一句话记忆点**:
> systemd 是 PID 1,用 `.service` 描述服务;`start`=现在跑、`enable`=开机跑、改了要 `daemon-reload`;`Restart` 自愈、`stop` 先 TERM 后 KILL、每个服务一个 cgroup 限资源;日志默认进 journald 用 `journalctl` 查。

**四语言桥接**(把你的程序变成正经服务,`ExecStart` 各写一例):

| 运行时 | `ExecStart=` |
|--------|--------------|
| Java | `/usr/bin/java -XX:MaxRAMPercentage=75 -jar /opt/app.jar` |
| Go | `/opt/app/server`(编译好的二进制,前台运行) |
| Python | `/opt/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000` |
| Node | `/usr/bin/node /opt/app/server.js`(别用 pm2 再套一层,交给 systemd) |

→ 优雅关闭对接 [`03` SIGTERM](../03-process-model/);资源限制就是 [`04` cgroup](../04-memory-model/) + [`05` fd 上限](../05-io-and-files/)。**其实 K8s 在很多方面就是「分布式的 systemd」**:拉起、守护、健康检查、资源限制、滚动——理解了 systemd,K8s 的 Pod 生命周期会很好懂(接 `09`)。

**延伸指针**:
- 日志基础设施 / 结构化日志 → `performance-tuning-roadmap/03-observability/01-structured-logging.md`、`02-log-infrastructure.md`
- 监控告警与 oncall → `performance-tuning-roadmap/03-observability/06-alerting-oncall.md`、`performance-tuning-roadmap/13-sre/`

➡️ 下一章:[`09 · 容器底层(Linux 视角)`](../09-containers-from-linux/)(systemd 限资源用的 cgroup、隔离用的 namespace,正是容器的两大基石)
