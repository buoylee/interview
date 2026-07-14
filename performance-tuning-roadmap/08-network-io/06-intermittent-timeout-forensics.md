# 随机请求超时的无值守取证

> 目标：随机 timeout 出现时，不需要工程师守在终端；系统自动保留事发前后有界证据，并把问题定位到 Client 应用、容器/TCP、Server 应用或 HTTP/2 stream。

## 一、问题边界

一次 `writeAndFlush()` 成功不证明 TCP ACK、对端 TLS/HTTP2 pipeline 或业务 handler 已处理。一次 `ss` 快照和 timeout 后才启动的抓包，也无法可靠还原已经过去的随机故障。

```text
持续采集低成本信号
  → 固定容量 ring 循环覆盖
  → timeout event 自动触发
  → pin T-60s～T+60s
  → 生成 incident bundle
  → 采集继续运行
```

这个模型是一套持续开启的 flight recorder，而不是故障发生后才执行的命令清单。ring 只保留固定时窗和固定容量；触发器把事发前后的片段 pin 到独立 incident bundle 后，原 ring 立即继续循环采集，避免一个事件令后续事件失去证据。

**非目标：**

- 不永久保存完整 payload；只保留定位所需的元数据、有界采样和经过脱敏的片段。
- 不在应用容器中授予抓包权限；抓包、eBPF 和宿主机网络观察由受控的 node/host collector 完成。
- 不因单个指标正常就排除网络问题；必须用请求身份和同一时间线上的多层证据互证。
- 不重复讲解 Netty、`ss`、Docker、Kubernetes、TLS 或 HTTP/2 的通用教程；这里只定义超时取证所需的边界、信号和关联方法。

## 二、先建立可关联的请求身份

每个请求的 trace、结构化日志和 incident metadata 必须能够用以下字段关联：

```text
trace_id, request_id, HTTP/2 stream_id, channel_id,
connection generation, local IP:port, remote IP:port,
service/peer, pod UID/container ID, node, network namespace,
timeout stage/deadline, wall-clock event time, monotonic duration
```

1. High-cardinality identity belongs in logs/traces/incident metadata, never metrics labels.
2. In-process duration uses `System.nanoTime()` or equivalent monotonic clock.
3. Cross-Node correlation uses synchronized wall time; clock status/offset enters `manifest.json`.
4. Record application, pre-NAT, post-NAT, sidecar, and server-observed tuples separately.

`connection generation` 在 channel 重连或连接池槽位复用时递增，防止相同 `channel_id` 或 4-tuple 被错误拼接。incident bundle 的 `manifest.json` 还要记录采集主机、时区、时间同步源、触发时间、证据时窗、软件版本和每份证据的来源。

## 三、Client A：从提交到响应或超时

统一使用同一条请求时间线，不能只记录“开始”和“timeout”：

```text
A Client:
t0 request submit
t1 connection/channel acquired
t2 EventLoop enter
t3 transport write
t4 write future complete
t5 response headers/complete | timeout
```

Netty 埋点使用稳定 stage name，便于不同服务和版本生成同构时间线：

```text
rpc_submit, eventloop_enter, transport_write, transport_flush,
write_future_done, response_received | timeout
```

| Stage name | Boundary |
|---|---|
| `rpc_submit` | t0，请求提交 |
| `eventloop_enter` | t2，任务开始在 EventLoop 执行 |
| `transport_write` | t3，进入 transport write |
| `transport_flush` | flush 发起；与 write 分开记录 |
| `write_future_done` | t4，write future 成功或失败 |
| `response_received \| timeout` | t5，响应完成或 deadline 触发 |

采集策略按信号成本分层：

- 全流量记录有界、低基数 metrics，例如各阶段耗时直方图、timeout/错误计数、EventLoop 排队时间和连接池 acquire 延迟。
- 正常请求 trace 采样 1–5%；slow/error/timeout 请求 trace 采样 100%。采样决策应在请求结束时完成，确保 timeout 不被头部采样丢弃。
- 每个失败请求只写一份 structured failure snapshot，包含第二节身份、各 stage 时间戳/耗时、deadline、channel 状态、连接池状态和错误链；通过 incident ID 去重。
- 每个请求的 stage event 先进入进程内 bounded ring，不把无限事件排入 heap；timeout 触发时再将关联窗口导出。

`write_future_done` 成功只说明数据被当前 transport 接受，不能把它解释为 TCP ACK、服务端收到请求或 handler 已执行。连接获取 `t1` 也必须单列，避免把连接池等待误判为网络传输耗时。

## 四、Transport/Container B：从用户态到对端内核

把 Client 应用之外、Server framework receive 之前的路径视为独立的 transport 边界：

```text
B transport:
userspace → socket send buffer → TCP/qdisc
→ container netns/veth → bridge/CNI/overlay
→ host NIC/network → peer kernel
```

对命中请求连接记录 `socket state`、`Send-Q`、`wmem_queued`、`notsent`、`bytes_sent`、`bytes_acked`、`unacked`、`retrans`、`RTT`、`RTO`、`cwnd`。这些值必须附带采集时刻、network namespace、4-tuple 和 connection generation，才能与 A/C 时间线正确对齐。

对于数量小且已知的连接池，优先使用 Netty native epoll `TCP_INFO`，在 timeout snapshot 中直接取得目标 socket 的内核状态；其他场景以 local port 为键使用 `ss -tinm` 作为 fallback。`ss` 观察的是 socket/连接，无法识别某个 HTTP/2 stream，不能仅凭它把同一连接上的某条失败 stream 定位为 TCP 故障。

持续低成本计数器用于发现时间窗，目标 socket 快照用于关联请求，ring pcap/eBPF flow event 用于还原包和内核路径。三者都要在 timeout 之前已运行，并受容量、时窗、过滤器和隐私策略约束。

## 五、Server C：拆开接收、排队和执行

服务端时间线必须与 Client/transport 时间线使用相同的 trace/request 身份：

```text
C Server:
t6 framework/network receive
t7 handler queued
t8 handler start
t9 handler finish
t10 response write complete
```

必须把 framework/network receive 与 handler start 分开记录。若 `t6` 已出现而 `t8` 很晚，问题在服务端排队或调度；若服务端完全没有 `t6`，才继续沿 B 层连接和网络证据缩小范围。异步框架还应分别记录 EventLoop 回调、业务 executor 提交和执行时间，避免把两类队列合并。

同一窗口至少保留这些有界信号：

- executor active/max、queue/rejection；
- event-loop lag；
- DB/HTTP pool pending/acquire latency；
- lock wait；
- GC pause；
- CPU throttling。

`t10 response write complete` 同样只是服务端 transport 的写完成边界，不等于 Client 已读取。服务端 failure snapshot 应包含 handler 结果、响应写 future、连接状态，以及与依赖池和运行时信号的 incident 时间窗链接。

## 六、Docker、Kubernetes 路径与指标映射

先把请求所在的 cgroup、netns、veth、节点和 service translation 逐跳解析出来，再选择采集点。不要把“容器网络”当作单一黑盒。

```text
Docker:
container cgroup → container netns eth0 → host veth
→ docker bridge/overlay → iptables/NAT/conntrack → host NIC

Kubernetes:
pod cgroup/netns → pod veth → CNI datapath
→ kube-proxy/IPVS/iptables 或 eBPF service translation
→ overlay/underlay → sidecar/Ingress → node NIC
```

incident metadata 应保存 pod UID/container ID 到 PID、cgroup、netns inode、host veth、node 和 workload revision 的映射。滚动发布、容器重启或 pod 漂移后，不能只用易复用的 pod 名或容器名回查历史证据。

| Layer | Signal | Common metric/example |
|---|---|---|
| Container CPU | throttled time/ratio | `container_cpu_cfs_throttled_seconds_total`, throttled periods / total periods |
| Container memory | working set/OOM/restart | `container_memory_working_set_bytes`, container restart/OOMKilled status |
| Container network | RX/TX drops/errors | container receive/transmit dropped packets and errors |
| Host veth/NIC | interface drops/errors | `node_network_receive_drop_total`, `node_network_transmit_drop_total` |
| Softnet | backlog drops | `node_softnet_dropped_total` |
| Conntrack | entries/limit/insert failures | `node_nf_conntrack_entries`, `node_nf_conntrack_entries_limit`, `conntrack -S` |
| TCP | retrans/RTO/SYN retrans | `node_netstat_Tcp_RetransSegs`, `node_netstat_TcpExt_TCPTimeouts`, `node_netstat_TcpExt_TCPSynRetrans` |
| CNI/overlay | drop/policy/MTU/encapsulation | CNI metrics and flow/drop-reason logs |
| Sidecar/proxy | connect fail/timeout/reset/retry/flow control | Envoy upstream connection/request/flow-control counters |

精确名称会随 runtime、cAdvisor、kernel、CNI 和 proxy 改变；部署前必须核对实际 `/metrics` 输出，不能只按表中名字配置告警。指标负责显示异常时间窗和范围，不携带 request ID、4-tuple 或 stream ID 这类高基数身份。

## 七、HTTPS/TLS/HTTP2 的证据边界

- TCP ACK proves peer kernel receipt, not TLS decode or handler execution.
- Encrypted pcap still shows TCP handshake, ACK, retransmission, RST, window, timing; not method/path/body without session keys.
- Record TLS termination and each service-mesh hop as separate connections.
- Persist `stream_id → channel_id/generation/4-tuple`.
- Inspect flow-control windows, `WINDOW_UPDATE`, `RST_STREAM`, `GOAWAY`.
- One failed stream with healthy siblings suggests stream/handler/deadline; many failed streams with Send-Q/retrans suggests connection/TCP.

TLS 在 sidecar、Ingress、gateway 或应用终止时，每一段都是不同的 TCP connection generation 和 4-tuple。incident bundle 要分别保存各 hop 的握手/连接错误、代理计数器和时间窗口，不能把入口连接的 ACK 当作后端应用连接的 ACK。

HTTP/2 multiplexing 要同时从请求维度和连接维度判断：单条 stream 的 deadline、`RST_STREAM` 或 handler 延迟不应污染整个 channel 的结论；连接级 `GOAWAY`、flow-control stall、Send-Q 增长或多条 sibling stream 同时失败，才支持把范围提升到 HTTP/2 connection 或 TCP。只有在受控环境且符合密钥和隐私策略时，才把 TLS session keys 加入加密 incident bundle；没有密钥的 pcap 仍然是有效的传输层证据。
