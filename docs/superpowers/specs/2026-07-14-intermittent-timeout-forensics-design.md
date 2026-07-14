# 随机请求超时无值守取证 Runbook 设计

**状态：** 已批准
**日期：** 2026-07-14
**目标文档：** `performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md`

## 1. 背景

现有 `04b-java-debugging/06-netty-performance.md` 第 9 节已经覆盖“高峰期单条长连接偶发发送超时”：按 `RPC submit → EventLoop → Pipeline → ChannelOutboundBuffer → kernel TCP → 对端 handler` 拆分发送路径，并要求在 timeout 时输出结构化快照。

当前缺口不是另写一套 Netty 排查方法，而是补齐生产环境的无值守证据保留机制：

- timeout 随机出现，人工无法守在终端等待；
- timeout 后再运行 `ss`、eBPF 或抓包，关键现场通常已经消失；
- HTTPS/TLS、HTTP/2 多路复用、容器 network namespace、NAT、CNI 和 sidecar 会改变观察点；
- 全量日志、Trace 或 pcap 长期落盘可能拖垮 Collector、业务磁盘或日志平台；
- “没有看到重传”可能是取证工具丢数据，不一定是网络正常。

因此新增独立生产 Runbook，将现有 Netty、Tracing、TCP 和抓包章节组合成一条可执行证据链。

## 2. 目标

1. 给出无人值守捕获随机 timeout 的生产方案：持续低成本采集、固定容量循环覆盖、timeout 自动触发、保留事发前后时间窗。
2. 通过 Client 应用、Kernel/容器/TCP、Server 应用三层时间线，区分：
   - Client EventLoop、线程池、连接池或 outbound pipeline；
   - 容器 CPU throttling、veth/CNI/overlay、conntrack；
   - TCP 丢包、重传、接收窗口、对端停止读取；
   - Server queue、锁、DB/下游或业务代码；
   - TLS、HTTP/2 stream flow control、RST_STREAM/GOAWAY。
3. 给出明确的容量、速率、TTL、安全和降级约束，避免取证系统成为新的事故来源。
4. 给出故障注入和验收标准，确保每类故障能产生不同、可验证的证据签名。
5. 保持现有文档单一职责，通过回链复用原理和工具细节，避免复制整章内容。

## 3. 非目标

- 不实现特定公司的完整 capture agent、事件总线或对象存储服务。
- 不把应用进程变成 privileged packet capture agent。
- 不长期保存完整 request/response payload。
- 不用单个主机级 metric 宣称“100% 排除网络”。
- 不承诺跨所有云厂商、CNI、service mesh 的统一指标名；正文描述稳定观察点，具体产品指标作为映射示例。
- 不把通用 Runbook 扩写成 Netty、OpenTelemetry、Wireshark 或 Kubernetes 的完整教程。

## 4. 核心决策

### 4.1 新建独立章节

新建：

`performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md`

采用“按证据时间线”组织，而不是按工具罗列：

```text
Client submit/write
  → userspace / EventLoop / Pipeline
  → kernel socket / TCP
  → container netns / veth
  → Docker bridge 或 Kubernetes CNI/overlay
  → host NIC / network
  → peer container/kernel
  → Server receive / queue / handler
```

工具命令放到末尾速查，避免值班人员从工具出发盲查。

### 4.2 基准环境

可执行示例以以下环境为基准：

```text
Linux
Docker 与 Kubernetes
Java/Netty client
Prometheus/Grafana
OpenTelemetry Collector
集中式日志平台
```

其他语言和平台只说明等价观察点，不复制多套代码。

### 4.3 黑盒/飞行记录器模式

```text
持续采集低成本信号
  → 固定大小 ring buffer 循环覆盖
  → timeout structured event 触发
  → 等待 T+ 时间窗结束
  → pin T-60s ～ T+60s 证据
  → 上传 incident storage
  → ring capture 继续运行
```

不要求人等待 timeout，也不在 timeout 后才启动采集。

## 5. 文档职责边界

| 文档 | 职责 |
|---|---|
| `04b-java-debugging/06-netty-performance.md` | Netty 阶段埋点、`ChannelFuture`、EventLoop、Channel 状态和单案例证据签名 |
| `08-network-io/01-tcpdump-wireshark.md` | capture filter、network namespace 抓包、Wireshark 分析 |
| `08-network-io/03-packet-loss-latency.md` | 重传、RTT、MTU、NIC/kernel drop |
| `03-observability/05-distributed-tracing.md` | Head/Tail Sampling 原理与 Collector 配置 |
| `03-observability/07-concurrent-resource-saturation.md` | EventLoop、线程池、连接池等并发饱和诊断树 |
| 新 Runbook | 将上述能力组合成随机 timeout 的无人值守采集、保留、关联和判定流程 |

新 Runbook 可以给出最小可运行配置，但通过链接解释完整原理。

## 6. 关联模型

### 6.1 必需关联键

每次 outbound request 至少保留：

```text
trace_id
request_id
HTTP/2 stream_id（适用时）
channel_id
connection generation
local IP:port
remote IP:port
service / peer
pod UID 或 container ID
node
network namespace identity
timeout stage / deadline
wall-clock event time
monotonic duration
```

`trace_id`、`request_id`、`channel_id`、端口等高基数字段只进入 logs/traces，不进入 Prometheus label。

### 6.2 多观察点 tuple

Docker/Kubernetes、NAT、sidecar 和 service mesh 会改变四元组。Manifest 必须允许记录每一跳看到的 tuple：

```text
application remoteAddress
app → local sidecar
sidecar → peer sidecar/service
pre-NAT tuple
post-NAT tuple
server-observed peer tuple
```

不能假设应用 `remoteAddress()` 等于 host NIC 或 server 看到的连接。必要时用 conntrack/NAT mapping 关联。

### 6.3 时间

- 进程内阶段耗时使用 monotonic clock，例如 `System.nanoTime()`。
- 跨进程、跨 Node 关联使用 wall clock。
- Node 使用 NTP/chrony；incident manifest 记录已知 clock offset 或同步状态。

## 7. 三层证据设计

### 7.1 A：Client 应用层

每个 request 在内存中保存阶段时间线：

```text
t0 request submit
t1 connection/channel acquired
t2 EventLoop enter
t3 transport write
t4 write future complete
t5 response headers/complete 或 timeout
```

保存策略：

- Metrics 全量记录阶段 latency、timeout stage 和有限枚举 cause。
- 正常 Trace 采样 1–5%。
- Slow/error/timeout Trace 100% 保留。
- 详细 structured log 只在 slow/error/timeout 输出一次。
- 阶段事件先进入有界 request ring，禁止每个阶段同步写磁盘。

OpenTelemetry 使用 Tail Sampling 保留 ERROR 和超过阈值的 Trace，并配置 `memory_limiter`。所有属于同一 Trace 的 spans 必须路由到能做一致采样决策的 Collector。

### 7.2 B：Kernel、TCP 与容器网络层

对于已知且数量有限的长连接，每秒采样一次、保留最近 30–60 秒：

```text
socket state
Send-Q / wmem_queued / notsent
bytes_sent / bytes_acked
unacked / retrans
RTT / RTO / cwnd
SO_SNDBUF / TCP_NODELAY（连接建立时记录）
```

Netty native epoll 可优先读取 `TCP_INFO`；`ss -tinm` 是按快照 local port 查 socket 的 fallback。`ss` 不是 request 级工具，也不能区分同一 HTTP/2 connection 内的 stream。

eBPF 持续捕获低频事件：

```text
tcp_sendmsg
tcp_retransmit_skb
TCP drop/reset
connect latency
socket state change
PID/cgroup/pod + observed 4-tuple
```

#### Docker 观察路径

```text
container cgroup
  → container netns eth0
  → host veth
  → docker bridge 或 overlay
  → iptables/NAT/conntrack
  → host NIC
```

#### Kubernetes 观察路径

```text
pod cgroup/netns
  → pod veth
  → CNI datapath
  → kube-proxy/IPVS/iptables 或 eBPF service translation
  → overlay/underlay
  → sidecar/Ingress（如有）
  → node NIC
```

#### 容器和 Node 指标意图

```text
container CPU throttling
container memory pressure/OOM/restart
event-loop lag
pod/container RX/TX packet、drop、error
host veth drop/error
softnet backlog drop
conntrack current/limit/insert failure
CNI drop/error/policy deny
overlay MTU/fragmentation/encapsulation error
sidecar upstream connect timeout/reset/retry
HTTP/2 flow-control pause/backed-up
```

正文给出常见 Prometheus 指标映射，同时要求读者以实际 runtime、cAdvisor、CNI 和 proxy 暴露结果为准。

### 7.3 C：Server 应用层

Server 保存：

```text
t6 framework/network receive
t7 handler queued
t8 handler start
t9 handler finish
t10 response write complete
```

持续监控：

```text
executor active/max
executor queue/rejection
event-loop lag
DB/HTTP connection-pool active/pending/acquire latency
lock wait
GC pause
CPU throttling
```

必须区分“framework 已收到”与“handler 真正开始”，否则线程池 queue delay 会被误判为网络或业务执行慢。

## 8. HTTPS、TLS 与 HTTP/2

- TCP ACK 只证明 peer kernel 收到，不证明 TLS 解密、HTTP/2 decoder 或业务 handler 已处理。
- HTTPS 未解密时，pcap 仍可分析 TCP handshake、ACK、重传、RST、window 和时间；不能看到 method、path、header 或 body。
- Manifest 记录 TLS termination 点；service mesh 下 app→sidecar 与 sidecar→peer 通常是不同连接。
- HTTP/2 必须记录 `stream_id → channel_id/generation/4-tuple` 映射。
- Connection-level `TCP_INFO` 不能解释单个 HTTP/2 stream；同时检查 stream/connection flow-control window、`WINDOW_UPDATE`、`RST_STREAM`、`GOAWAY`。
- 单个 stream timeout 且同 connection 其他 stream 正常，优先查 stream flow control、handler、deadline/cancel；多个 stream 同时异常并伴随 Send-Q/retrans，才更支持 connection/TCP 问题。

## 9. 三种有界 Ring

| Ring | 内容 | 位置 | 默认保留 |
|---|---|---|---|
| Request ring | Client/Server 阶段事件 | 进程内存 | 每连接/每请求最近 30–60 秒 |
| TCP ring | 每连接 `TCP_INFO` 样本 | 进程或 Node agent | 最近 30–60 秒 |
| Packet ring | packet header | Node 专用 volume | 固定文件数和总容量 |

Packet ring 使用 `dumpcap`，同时限制：

```text
capture filter：指定服务 IP/port
snaplen：128 bytes
rotation：30 秒或 100 MB
files：20
上限：约 2 GB/Node
```

高流量时可能先触发 filesize，实际时间覆盖短于预期。必须监控 `oldest_capture_timestamp` 与 `effective_retention_seconds`，不能只按文件数推断保留时间。

需要双端定向取证时，在 Client Node 与 Server Node 分别保留同一时间窗；单端 pcap 无法可靠判断方向性丢包。

## 10. 自动触发与 Incident Bundle

### 10.1 组件

1. **Application instrumentation**：生成 timeout structured event 和 A/C 层快照。
2. **OTel/log pipeline**：保留 timeout Trace/log，并传递 trigger 所需字段。
3. **Node capture agent**：负责 eBPF、packet ring、pin；与应用权限隔离。
4. **Incident correlator**：去重、等待 T+ 窗口、请求相关 Node pin 文件。
5. **Incident storage**：保存 bundle，执行 TTL、RBAC、审计和删除。

### 10.2 Trigger event

```text
event_time
service / peer
node
pod UID / container ID
network namespace identity
trace_id / request_id
stream_id
channel_id / connection generation
local/remote 4-tuple
timeout stage / deadline
```

应用不能传入任意 BPF filter，也不能直接执行 shell。Capture agent 只使用预先批准的 service/port policy。

### 10.3 数据流

```text
Client timeout
  → timeout event
  → correlator dedupe
  → 等待 T+60s
  → pin Client/Server Node 的 T-60s～T+60s
  → 合并 Trace、logs、TCP/eBPF、container metrics、pcap
  → 写 incident storage
  → capture ring 继续运行
```

### 10.4 Bundle

```text
incident/<trace_id-or-incident-id>/
├── manifest.json
├── client-timeout.json
├── trace.json
├── server-events.json
├── tcp-ebpf.json
├── container-metrics.json
├── client-node.pcapng
└── server-node.pcapng
```

`manifest.json` 记录：

```text
clock sync/offset
观察点和每跳 tuple
TLS termination 点
capture filter/snaplen/tool version
pcap packets dropped by kernel
eBPF lost events
OTel/log exporter drops
缺失文件及失败原因
```

## 11. 容量、降级与安全

### 11.1 默认控制

```text
pcap ring：约 2 GB/Node
pin window：T-60s～T+60s
dedupe：同 service/node/peer/cause，5 分钟一次
pin rate limit：每 Node 每小时 3 次
incident TTL：3 天
storage：专用 volume + quota
```

这些是文档示例默认值；实际部署必须用流量测算调整。

### 11.2 触发风暴降级

优先级：

1. timeout metrics/logs 全保留；
2. error/slow Trace 全保留；
3. eBPF 事件继续，但允许聚合；
4. pcap 只 pin 首次或代表样本；
5. 正常 Trace 优先丢弃；
6. capture 不得侵占业务磁盘安全水位。

### 11.3 安全

- 默认不保存 body、token、cookie、Authorization header。
- Packet、Trace 和 logs 使用 RBAC、审计、传输/静态加密和固定 TTL。
- Capture agent 最小权限运行；应用容器不获得抓包权限。
- Filter 来自静态 allowlist，禁止通过 timeout event 注入任意表达式。
- Incident bundle 导出必须记录访问者、用途和删除时间。

## 12. 取证系统自监控

必须监控：

```text
OTel received/dropped spans
Tail Sampling decision latency/trace count/memory
log exporter queue/drop
eBPF lost events
pcap packets received/dropped by kernel
capture agent health/restart
ring disk usage
oldest capture timestamp/effective retention
trigger received/deduped/rejected
pin success/failure/latency
incident storage upload failure
```

如果这些数据缺失，结论必须写“无证据”，不能写“未发生”。

## 13. 证据判定矩阵

| 证据签名 | 优先故障边界 |
|---|---|
| `t1-t0` 高，EventLoop lag/pendingTasks 同时高 | Client EventLoop 或任务排队 |
| write future pending，pending bytes 上升，Channel 不可写 | Netty outbound backpressure |
| write future success，但没有对应 `tcp_sendmsg`/`bytes_sent` 变化 | 自研 promise/pipeline、连接映射或观察点错误 |
| `bytes_sent` 增加，`bytes_acked` 停止，retrans/RTO 增加 | TCP、网络或对端 ACK 路径 |
| `bytes_acked` 增加，Server framework 没有 request | Server socket/TLS/HTTP2 pipeline、trace 传播或观察点 |
| Server receive→handler start 高，executor queue 高 | Server 线程池/并发排队 |
| handler start→finish 高 | 业务代码、锁、DB 或下游 |
| Server response write 完成，Client 未收到 | 回程网络、proxy 或 Client read/EventLoop |
| 单个 HTTP/2 stream timeout，其他 stream 正常 | Stream flow control、RST、handler、deadline/cancel |
| 同 connection 多 stream 同时 timeout，Send-Q/retrans 异常 | Connection/TCP 层 |
| CPU throttling 与 EventLoop lag 同时高 | Container CPU quota |
| pod veth/CNI/softnet drop 增加 | Container/Node datapath |
| conntrack 接近上限或 insert failure | NAT/conntrack 路径 |

结论格式：

```text
主要根因：
支持证据：
排除证据：
尚缺证据：
信心：高 / 中 / 低
```

禁止从以下单一现象下结论：

- retrans metric 没涨，所以 100% 不是网络；
- pcap 没看到 request，所以 Client 没发；
- write future success，所以 Server 已收到；
- TCP ACK 到达，所以业务 handler 已处理。

## 14. 值班 Runbook

```text
1. 取得 trace_id、stream_id、channel/connection identity、4-tuple、timeout stage。
2. 打开自动生成的 incident bundle，先检查 manifest 的缺失/丢失指标。
3. 排 A：Client 阶段时间线，找第一个异常 gap。
4. 排 B：TCP、container、CNI、sidecar 和对应 Node 时间线。
5. 排 C：Server receive、queue、handler、response write 时间线。
6. 比较同 Node、同 EventLoop、同 connection 的其他 request/stream。
7. 只针对未解释区段查看双端 pcap。
8. 记录主要根因、证据、缺失证据和信心。
```

## 15. 故障处理

- Trigger 丢失：timeout metric 与 trigger count 对账，告警并保留应用 log/trace。
- Tail Sampling 过载：优先保留 ERROR/slow，丢弃正常 Trace；Collector 启用 memory limiter。
- eBPF ring/event 丢失：输出 lost event counter，结论标注该证据不可用。
- pcap kernel drop：增加 capture buffer、缩窄 filter；bundle 标明 drop 数。
- 磁盘达到安全水位：停止 pin 或缩短 TTL，不得挤占业务磁盘。
- T+ 文件仍在写：等待 rotation 完成后 pin；至少先保留已关闭的 T- 文件。
- Client/Server Node 已销毁：保留现有 Trace/log/eBPF；明确缺失的端点证据。
- 时钟不同步：使用各进程 monotonic duration，并在跨主机结论中降低信心。

## 16. 故障注入与验收

### 16.1 测试场景

1. EventLoop handler 人为阻塞。
2. Executor queue 饱和。
3. Container CPU quota/throttling。
4. 对端停止 `read()`。
5. `tc netem` 注入 loss、latency、reorder。
6. HTTP/2 stream window 归零。
7. `RST_STREAM`/`GOAWAY`。
8. Sidecar reset/connect timeout。
9. CNI/overlay MTU 错配。
10. Capture pipeline 自身丢 spans/events/packets。

### 16.2 验收标准

- 每种故障无需人工等待即可生成 incident bundle。
- timeout 后 2 分钟内完成或明确报告 bundle 生成失败。
- 每种故障产生预期且可区分的证据签名。
- Packet ring 不突破配置 quota。
- Trigger 风暴不拖垮业务、Collector 或 Node 磁盘。
- 取证工具丢数据时有告警，bundle 明确标注。
- Bundle 不含 body、token、cookie 或敏感 header。
- 值班人员能在 10 分钟内将问题归类到 Client 应用、容器、TCP/网络、Server 应用或 HTTP/2 stream。

## 17. 文档变更范围

### 新文件

- `performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md`

### 回链修改

- `performance-tuning-roadmap/08-network-io/README.md`
  - 加入第 6 章、目标能力和交付物。
- `performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md`
  - 第 9 节增加无值守保留回链；保留 Netty 专属埋点，不复制通用 Runbook。
- `performance-tuning-roadmap/08-network-io/03-packet-loss-latency.md`
  - 偶发 timeout 决策树链接新 Runbook。
- `performance-tuning-roadmap/08-network-io/01-tcpdump-wireshark.md`
  - 长时间轮转抓包段链接自动 pin、quota 与 incident bundle。
- `performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md`
  - Netty outbound 分支链接新 Runbook。

## 18. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 新 Runbook 与现有章节重复 | 只保留最小配置和事故编排；原理通过回链复用 |
| 指标名依赖 runtime/CNI/proxy | 先写稳定观察点，再列常见映射并要求现场验证 |
| 全量取证成本过高 | 有界 ring、Tail Sampling、event-driven eBPF、dedupe、rate limit、TTL |
| 单端证据误判方向 | 需要时 pin Client/Server 双端；manifest 标观察点和 NAT tuple |
| HTTP/2 stream 被 TCP 聚合掩盖 | 强制保存 stream→connection 映射和 flow-control/RST/GOAWAY |
| 取证系统丢数据造成错误排除 | 对采集链路做自监控；缺失时结论写“无证据” |
| 敏感信息泄露 | snaplen/filter、禁止 body/header、RBAC、审计、加密、TTL |

