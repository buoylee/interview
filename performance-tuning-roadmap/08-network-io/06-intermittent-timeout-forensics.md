# 随机请求超时的无值守取证

> 目标：随机 timeout 出现时，不需要工程师守在终端；系统自动保留事发前后有界证据，并把问题定位到 Client 应用、容器/TCP、Server 应用或 HTTP/2 stream。

## 一、问题边界

一次 `writeAndFlush()` 成功不证明 TCP ACK、对端 TLS/HTTP2 pipeline 或业务 handler 已处理。一次 `ss` 快照和 timeout 后才启动的抓包，也无法可靠还原已经过去的随机故障。

```text
持续采集低成本信号
  → 固定容量 ring 循环覆盖
  → timeout event 自动触发
  → 立即 freeze/copy T-60s～T 的 closed records/segments
  → protected evidence append T～T+60s
  → rotation close 后 finalize
  → 生成 incident bundle
  → 采集继续运行
```

这个模型是一套持续开启的 flight recorder，而不是故障发生后才执行的命令清单。ring 只保留固定时窗和固定容量；trigger 必须先保护已存在的前窗，再收集后窗，不能等到 T+60 才回头读取已经被覆盖的 ring。protected evidence 使用独立的 quota/reference，原 ring 始终继续循环采集，避免一个事件令后续事件失去证据。

**非目标：**

- 绝不采集或保存 request/response body、token、cookie、`Authorization` header、TLS session keys 或任何其他 secret；只保留不含秘密的定位元数据和有界传输层信号。
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

所有 logs、traces、events、snapshots 与 bundle JSON 必须执行 allowlisted evidence schema，只接受：

- 本节定义的 identity metadata；
- stage timestamps 与 monotonic durations；
- bounded enum `stage`、`status`、`result`、`error_code`、`timeout_stage`；
- bounded numeric socket、queue、pool、runtime、container 与 collection-health counters；
- versioned observation-point、mapping、tool/policy/schema metadata，canonical artifact status 与 bounded failure reason；
- safe exception class/code，或在进程内只从 approved frame identifiers 生成的 normalized stack fingerprint；fingerprint 输入和输出都绝不包含 message/value。

Handler result 只能写 bounded outcome；error chain 只能写 approved class/code/fingerprint。禁止 free-form exception/error/stack message、URL/query、headers、body、`db.statement` 和任何 payload-derived fragment。Invalid/unmapped event value 必须在 admission 时拒绝并以 bounded reason 计数，绝不把被拒值或 message/value 写入任何 log、trace、event 或 bundle。

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
- 使用第九节 Collector Tail Sampling pipeline 时，upstream SDK/agent 必须完整 export 候选 traces，典型配置为 `AlwaysOn` 或 `ParentBased(AlwaysOn)`；禁止先做 1–5% head sampling。1–5% 仅表示 Collector 最终对 normal traces 的 retention，slow/error/timeout 的 100% 也只是满足完整性前提时的 policy intent。
- 每个失败请求只写一份 structured failure snapshot，包含第二节 allowlisted identity、stage timestamp/duration、deadline、bounded channel/pool state，以及 approved error class/code/normalized stack fingerprint；通过 incident ID 去重。
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

必须把 framework/network receive 与 handler start 分开记录。若 `t6` 已出现而 `t8` 很晚，问题在服务端排队或调度。只要 A→t6 gap 异常，无论 `t6` 是延迟出现还是缺失，都要检查 B 层连接和网络证据。缺失的 `t6` 只有在服务端埋点覆盖完整且 collection health（采集、导出、采样、保留）已验证健康后，才算“absence 的证据”；否则必须标记为“no evidence / unavailable evidence（无证据／证据不可用）”，不能据此推断请求未到达服务端。异步框架还应分别记录 EventLoop 回调、业务 executor 提交和执行时间，避免把两类队列合并。

同一窗口至少保留这些有界信号：

- executor active/max、queue/rejection；
- event-loop lag；
- DB/HTTP pool pending/acquire latency；
- lock wait；
- GC pause；
- CPU throttling。

`t10 response write complete` 同样只是服务端 transport 的写完成边界，不等于 Client 已读取。服务端 failure snapshot 的 handler result 只能是 bounded outcome；错误只允许 approved class/code/normalized stack fingerprint，另附 bounded response-write、connection、dependency-pool、runtime counters 与 incident 时间窗链接。

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

### 6.1 预计算双端 Node 定位索引

不能等 timeout 后才解析 Server Node。Correlator 必须在平时持续维护 time-versioned correlation index，并保存 mapping version、valid-time window、source freshness 与授权状态：

```text
Client tuple/netns @ event_time
  → conntrack/NAT pre/post tuple
  → sidecar inbound/outbound hop
  → Kubernetes EndpointSlice + Service route + CNI flow
  → candidate Server pod UID/node/observed tuple
```

Timeout trigger 到达时，correlator 在 retention margin 内查询 event-time 对应的 index version，并立即 fan-out protect 到 Client Node 与所有同时命中 index 和 static allowlist 授权的 candidate Server Nodes；不得等待 Trace 或 Server framework event 才开始保护。Server framework receive 可以发送 mirrored server preservation signal 补强已授权 candidate 的定位，但不能成为前窗保护的前置条件。

Event input 只能提供第九节 required identity，绝不能指定任意 Node、candidate 或 filter。Fan-out target 只能来自 time-versioned index 的候选集合与 static allowlist 交集。`peer`/`remote_tuple` 可能是 VIP、NAT 地址或 sidecar，禁止假定它唯一对应一个 Server Node。

Mapping stale、ambiguous、unresolved 或 fan-out timeout 时，manifest 必须把对应 Server artifact 标为 `partial` 或 `unavailable`，并记录 index version、mapping age、全部授权 candidates、选中/未命中 Node 与 bounded reason；不能把 Client 端证据包装成完整双端证据。

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

HTTP/2 multiplexing 要同时从请求维度和连接维度判断：单条 stream 的 deadline、`RST_STREAM` 或 handler 延迟不应污染整个 channel 的结论；连接级 `GOAWAY`、flow-control stall、Send-Q 增长或多条 sibling stream 同时失败，才支持把范围提升到 HTTP/2 connection 或 TCP。禁止采集 TLS session keys；没有 session keys 时，加密 pcap 无法提供 payload，但仍然是有效的传输层证据。

## 八、三种有界 Ring 与双端保留

以下默认值面向 Linux + Docker/Kubernetes + Netty + Prometheus/OpenTelemetry 基准环境。三个 ring 必须在 timeout 前持续运行，并分别限制内存、磁盘和时间范围：

| Ring | Content | Location | Default |
|---|---|---|---|
| Request | A/C stage events | process memory | recent 30–60s per active connection |
| TCP | `TCP_INFO` samples | process/Node agent | recent 30–60s |
| Packet | headers | dedicated Node volume | bounded by duration, size, count, quota |

表中的 30–60 秒只是成本 baseline，不是完整 incident window 的保证。要支持默认 `T-60s`，Request、TCP 与 Packet ring 的 **effective pre-retention 必须至少为 60 秒，加上 trigger propagation、freeze/pin 与 rotation margin**；部署值必须由实测覆盖。任何 ring 的实际 oldest timestamp/effective retention 短于所需前窗时，`manifest.json` 必须把对应 artifact 标为 `partial`、`unavailable` 或 `failure`，绝不能声称拥有完整 `T-60s～T+60s` 证据。

Packet ring 使用窄 capture filter；下面的 `192.0.2.10` 是文档示例地址，部署时只能替换为静态 allowlist 中已批准的服务 IP/port：

```bash
sudo dumpcap \
  -i any \
  -f 'tcp and host 192.0.2.10 and port 443' \
  -s 128 \
  -b duration:30 \
  -b filesize:102400 \
  -b files:20 \
  -w /var/capture/service.pcapng
```

这里的 packet defaults 必须同时成立：snaplen 为 128 bytes；filter 限定协议、目标和端口；每 30 秒或 100 MiB（`filesize:102400`）轮转，以先达到者为准；最多 20 个文件；总容量约 2 GiB/Node。高流量时 size rotation 会缩短时间覆盖，因此必须监控最旧文件时间和 effective retention，不能根据 20 个文件推断一定保留 10 分钟。Trigger 到达时 Node agent 必须立即保护所有覆盖 T− 窗口的 closed files，并为当前 open segment 建立 protected-on-close reference；如果 oldest timestamp 已晚于所需起点，bundle 只能标为 `partial`，并记录缺失范围。

**`dumpcap -s 128` 保存的是 raw packet prefix，不保证只含 L2/L3/L4 headers。** 可变长度 headers 之后仍可能出现应用 bytes；因此上面的 raw dumpcap ring 只能用于 static allowlist 中已经验证为“仍处于 TLS 加密边界内”的 observation hop，并且该 hop 禁止 TLS session keys、decryption 或任何 payload 解码。任何 cleartext hop 或 TLS termination 之后的 hop 都必须禁用 raw pcap，改用 approved eBPF/header-only capture agent：只输出解析后的 L2/L3/L4/TCP metadata，在持久化前丢弃全部 payload bytes；也可以只使用 `TCP_INFO`。这些 hop 不得产生 raw artifact。如果组织政策连 encrypted application bytes 都禁止，必须全面禁用 dumpcap ring。

Bundle admission 必须验证 observation hop、TLS boundary、policy version 与 static allowlist metadata。不合规或无法证明合规的 raw artifact 必须拒绝进入 bundle、立即销毁，并在 manifest 记录 `privacy_policy_rejected` failure；绝不能依赖 sanitized fragment 作为例外。

需要判断方向性时，Client Node 和 Server Node 都要运行 ring，并 pin 相同的 `T-60s～T+60s` 时窗。单端 pcap 无法可靠区分“发送端未发出”“中间路径丢失”和“接收端已收到但采集点错误”。

## 九、Tail Sampling 与 Trigger 契约

OpenTelemetry Collector 通过 Tail Sampling 选择异常 Trace。使用这条 pipeline 时，upstream SDK/agent 对候选 traces 必须完整 export，典型配置为 `AlwaysOn` 或 `ParentBased(AlwaysOn)`；禁止 upstream 先做 1–5% head sampling，否则被丢弃的 error/slow spans 不会到达 Collector。1–5% 是 Collector policy 对 normal traces 的最终 retention。所有属于同一 Trace 的 spans 还必须路由到能做一致决策的同一个 Collector；以下 memory/trace capacity 数值只是 **load-test-sized example**，必须按实际流量压测，不是通用 production sizing：

```yaml
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 2048
    spike_limit_mib: 512
  tail_sampling:
    decision_wait: 10s
    num_traces: 50000
    expected_new_traces_per_sec: 5000
    policies:
      - name: keep-errors
        type: status_code
        status_code:
          status_codes: [ERROR]
      - name: keep-slow
        type: latency
        latency:
          threshold_ms: 2000
      - name: sample-normal
        type: probabilistic
        probabilistic:
          sampling_percentage: 1
```

容量值必须用 production peak 和 Trace 生命周期校准，而不是把示例的 50,000 当成容量结论。最低 sizing 原则是：`num_traces >= peak new trace rate × effective decision residence × safety factor`。Safety factor 必须为 burst 与 Collector 抖动留出 margin，并通过压测校准 memory limiter、CPU 与 exporter backpressure。

Production `decision_wait` 必须独立校准，至少覆盖 trace completion latency + SDK/exporter/network lateness + safety margin；只增加 `num_traces` 不能让已完成 decision 重新纳入 late span。Decision 完成后到达的 span 不参与该次 policy decision。必须监控实际版本提供的 late-span 信号，官方常见名称包括 `otelcol_processor_tail_sampling_sampling_late_span_age`，并计算 late-span ratio；指标名称与单位必须按部署 Collector 版本验证。

Policy intent 不可弱化：error 和 slow requests 由 keep policy 选中，normal requests 才按比例采样。但 trace artifact 只有同时验证以下条件时才能标为 `complete`：upstream candidate complete export；同 Trace 一致路由到同一 Collector；所有 policy-relevant spans 在 decision 前到齐；early drop、overflow、policy evaluation error 均为零。任一条件未验证或异常，canonical artifact status 必须是 `partial` 或 `unavailable`，不得保证 error/slow trace retained。完整配置语义见[本章分布式链路追踪](../03-observability/05-distributed-tracing.md#tail-based-sampling尾部采样)与[官方 Tail Sampling Processor README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/tailsamplingprocessor/README.md)。

应用只发出 timeout trigger event，字段必须完整且命名稳定：

```text
event_time, service, peer, node, pod_uid/container_id,
network_namespace, trace_id, request_id, stream_id,
channel_id, connection_generation, local_tuple, remote_tuple,
timeout_stage, deadline
```

`trace_id`、`request_id`、`stream_id`、channel/connection identity 和 tuples 只进入 logs、traces、trigger events 与 incident metadata，禁止成为 Prometheus/OpenTelemetry metrics labels。应用不得抓包、加载 eBPF、执行 shell 或提交 filter；privileged Node agent 独占 eBPF/pcap 的启动、轮转和 pin 权限。Agent 的 filter 只能从本地静态 allowlist 选择，绝不读取、拼接或执行 event input。

Required trigger fields 不新增 `cause`。Correlator 只根据 bounded `timeout_stage` enum 查表生成 bounded `normalized_cause`，并使用 `service/node/peer/normalized_cause` 作为 dedupe key。Free-form exception/error/stack message 和任意 event string 都不得参与 dedupe key，也不得成为 metric label；无法映射的 stage 必须拒绝并以 bounded `unknown` reason 计数，被拒 value 不得写入 log/trace/event/bundle。

## 十、触发流程、Bundle 与 Manifest

Correlator 用稳定的低基数字段做去重，并执行 two-phase preservation：先保护前窗，再等待并追加后窗。Application instrumentation 在 timeout 当下于进程内 freeze 有界 request snapshot，对 capture system 仍然只发 required trigger event；process-side evidence exporter 按 trigger identity 把 snapshot 复制到 protected incident staging。Correlator 立即查询 event-time 对应的 time-versioned index，在 retention margin 内 fan-out 到 Client Node 与所有 index ∩ static allowlist 的 candidate Server Nodes，不等待 Trace。各 privileged Node agent 随即 freeze/copy 覆盖 `T-60s～T` 的 closed TCP/eBPF/pcap segments/records，或建立不会被 ring overwrite 的 protected references；跨过 T 的当前 open segment 必须在 trigger 时标记为 protected-on-close。然后 incident staging 持续 append `T～T+60s`，直到 T+60 rotation close 后才 finalize/upload；原 ring 全程不停止。

```text
Client timeout → map normalized_cause → correlator dedupe
→ lookup event-time index version → fan-out authorized Client/candidate Server Nodes
→ T: freeze request snapshot + protect/copy T-60s～T closed evidence
→ append A/B/C + eBPF + container metrics + permitted pcap for T～T+60s
→ T+60 rotation close → finalize/upload bundle
→ protected refs released; original rings have continued throughout
```

上传成功或明确失败都不能暂停原 ring。每个 incident bundle 至少包含：

```text
incident/<incident-id>/
├── manifest.json
├── client-timeout.json       # Client timeout 与 A 时间线
├── trace.json                # Trace
├── server-events.json        # Server events 与 C 时间线
├── tcp-ebpf.json             # TCP_INFO/eBPF
├── container-metrics.json    # 容器、CNI、sidecar、Node 时间窗
├── client-node.pcapng        # Client pcap
└── server-node.pcapng        # Server pcap
```

两个 pcap 路径是 bundle 的逻辑 artifact slots，不表示每个 hop 都必须生成 raw 文件：只有通过 privacy admission 的 TLS-encrypted allowlisted hop 才能写入；cleartext、TLS termination 后、组织政策禁用或无法验证的 hop 不产生 raw artifact，slot 由 manifest 记录为 `unavailable`/`failure` 和原因，并以 metadata-only eBPF/TCP_INFO 证据替代。

`manifest.json` 是解释证据有效性的入口，必须记录：

- wall-clock 同步状态、已知 offset、时区，以及各进程 monotonic duration 的来源；
- Client/sidecar/pre-NAT/post-NAT/Server observation points、每一跳 tuple、netns 与 connection generation；
- correlation index version/valid time、mapping age/source、authorized candidates、fan-out target/result/latency；stale/ambiguous/unresolved/timeout 的 bounded reason；
- TLS termination 点，以及 app、sidecar、gateway 分段连接关系；
- capture policy/version、static allowlist match、raw/metadata-only mode、filter、snaplen、dumpcap/eBPF/Collector/agent 版本；
- 每个 ring 的 required/actual oldest timestamp、effective pre-retention、freeze/protect/rotation-close 时间与完整覆盖范围；
- pcap received/dropped、eBPF loss、OTel dropped spans、log exporter drops；
- upstream sampling/export mode、same-trace routing version、production `decision_wait`、policy error，以及依实际 Collector 版本验证过的 Tail Sampling early removal/drop/capacity-loss/late-span 指标，例如 `sampling_trace_dropped_too_early`、`otelcol_processor_tail_sampling_sampling_late_span_age`、trace removal age、late ratio 与 overflow；
- 每个应有 artifact 使用唯一 canonical schema：`artifact_status = complete|partial|unavailable|failure`；缺失或部分 artifact 必须附时间范围和明确 bounded failure reason。

如果 manifest 的 retention、preservation、privacy、loss/drop/clock 信息缺失，相应证据只能标为 unavailable；“没有采到”不能转写成“没有发生”。

## 十一、容量、过载、安全与自监控

### 11.1 固定默认值与触发风暴

```text
packet ring：snaplen 128、窄 filter、30 秒或 100 MiB、20 files、约 2 GiB/Node
incident window：T-60s～T+60s
dedupe：同 service/node/peer/normalized_cause，5 分钟一次
pin rate limit：最多 3 pins/Node/hour
incident TTL：3 天
storage：Node 专用 volume + quota + 业务磁盘安全水位
```

触发风暴时严格按以下顺序降级：

1. 保留 timeout metrics/logs。
2. 保留 error/slow traces。
3. 必要时聚合 eBPF，但继续暴露 loss counter。
4. pcap 只 pin 首次或代表样本。
5. 优先丢弃 normal traces。
6. 在触及业务磁盘安全水位前停止 pin；不得以业务可用性换取取证完整性。

达到 dedupe 或 rate limit 的 trigger 仍要计入 received/deduped/rejected 指标，并在相关事件中记录未 pin 原因。这里的 `normalized_cause` 只能由 bounded `timeout_stage` enum 映射；TTL 删除、quota 拒绝与上传失败同样必须可审计。

### 11.2 取证系统自身的健康度

至少自监控以下信号：

- OTel received/dropped spans；upstream export-mode/config drift、same-trace routing；Tail Sampling decision latency、trace count、memory、policy errors，以及按部署 Collector 版本核对过的 early removal/drop/capacity loss/late-span（例如 `sampling_trace_dropped_too_early`、`otelcol_processor_tail_sampling_sampling_late_span_age`、removal age、late ratio、overflow）；
- log exporter queue/drop；
- eBPF lost events；
- pcap packets received/dropped by kernel；
- capture agent health/restart；
- ring disk usage、oldest capture timestamp、effective retention；
- correlation index mapping age、resolution status/ambiguity、candidate count、fan-out latency/failure；
- trigger received/deduped/rejected；
- pin success/failure/latency；
- evidence-schema rejected/unmapped counts；
- incident storage upload failures。

Collector metric 名称和语义会随版本变化，部署前必须从实际 `/metrics` 与对应版本文档验证，不能因某个预期名称不存在就推断没有 early drop。上述 metrics 只能使用 service、node、result、bounded reason/`normalized_cause` 等有界枚举；不得加入 request、trace、stream、tuple、pod UID、connection identity、exception/error text 或任意 event string。任何一个正常的 aggregate metric 都不能单独证明“不是网络”；aggregate 信号只用于定位范围，结论必须回到同一请求的 A/B/C、双端观察点和 collection-health 证据。

### 11.3 安全与最小权限

- 绝不采集、缓存、pin、上传或导出 request/response body、token、cookie、`Authorization`、TLS session keys、secrets；即使宣称是 sanitized fragment 也不例外。
- Snaplen 128 只是 raw prefix 长度上限，不是 header-only 或隐私控制。Raw dumpcap 只允许在 static allowlist 中已验证仍在 TLS 加密边界、且禁止 session keys/decryption 的 hop；cleartext/TLS termination 后 hop 必须使用丢弃 payload bytes 的 approved metadata-only agent/eBPF 或 `TCP_INFO`，不得生成 raw artifact。若组织政策禁止 encrypted application bytes，则禁用所有 raw dumpcap。
- Bundle admission 必须核对 policy metadata、TLS boundary 与 allowlist；不合规 artifact 必须拒绝、立即销毁并在 manifest 留下 failure，不提供 sanitized fragment 例外。Trace/log/event 只能含第二节 allowlisted evidence schema 的字段和值。
- Incident storage 和传输必须启用 RBAC、访问/导出/删除审计、传输与静态加密、3 天 TTL。
- Node agent 只获得加载批准的 eBPF 程序、读取批准观察点和写专用 volume 的最小权限；应用容器永不获得 privileged capture 权限。
- Filter 只来自版本化的静态 allowlist，禁止从 trigger event、request 参数或其他动态输入生成。

### 11.4 采集故障处理

| Failure | Required handling |
|---|---|
| Trigger 丢失 | timeout metrics 与 trigger count 对账并告警；保留已有 application log/trace |
| Tail Sampling 过载 | 保留 ERROR/slow policy intent、先丢 normal traces；检查 `memory_limiter` 与 production sizing；early removal/drop/overflow 非零时将 trace 标为 `partial`/`unavailable` |
| Upstream head sampling 或 late span | 修正为完整 export，重新校准 `decision_wait`；已完成 decision 不回补，trace 标为 `partial`/`unavailable` |
| eBPF ring/event 丢失 | 输出 lost-event counter；manifest 标为 unavailable evidence |
| pcap kernel drop | 缩窄静态 filter、调整 capture buffer；manifest 记录 received/dropped |
| Effective pre-retention 不足 | trigger 当下先保护仍存在的 closed T− records/files；manifest 标 `partial` 并记录实际覆盖，禁止声称完整窗口 |
| Mapping stale/ambiguous/unresolved 或 fan-out timeout | Client 证据继续保护；Server artifact 标 `partial`/`unavailable`，记录 index version、candidates、mapping age 与 bounded reason |
| 磁盘达到安全水位 | 立即停止 pin 或按 policy 缩短 TTL；不得侵占业务磁盘 |
| T+ 文件仍在写 | T 时已经 freeze/protect 所有 closed T− 文件并标记 current segment 为 protected-on-close；持续 append 后窗，等待 T+60 rotation close 后 finalize |
| Raw artifact 不符合隐私 policy | admission 拒绝并立即销毁；manifest 记录 policy/version/hop 与 `privacy_policy_rejected` |
| Client/Server Node 已销毁 | 保留 Trace/log/eBPF 等现存证据；逐项记录缺失端点及原因 |
| 时钟不同步 | 使用进程内 monotonic duration；跨主机排序标注 offset 并降低信心 |
| Bundle 上传失败 | 在 2 分钟 SLA 内重试到上限后明确失败；ring 继续运行并告警 |

## 十二、证据判定矩阵

| Signature | Boundary |
|---|---|
| `t1-t0` high + pool pending/acquire latency high | Client connection pool/acquire queue |
| `t2-t1` high + EventLoop lag high | Client EventLoop queue |
| future pending + pending bytes rising + unwritable | outbound backpressure |
| future success + no `tcp_sendmsg`/`bytes_sent` delta | promise/pipeline/mapping/observation point |
| `bytes_sent` rises + `bytes_acked` stalls + retrans/RTO rises | TCP/network/peer ACK path |
| `bytes_acked` rises + no Server framework event | Server socket/TLS/HTTP2/trace/observation point |
| receive→handler start high + executor queue high | Server concurrency queue |
| handler duration high | code/lock/DB/downstream |
| Server response write complete + Client missing | return path/proxy/Client read |
| one HTTP/2 stream fails | stream/handler/deadline |
| many streams fail + Send-Q/retrans abnormal | connection/TCP |
| CPU throttling + EventLoop lag | container CPU quota |
| veth/CNI/softnet drops rise | container/Node datapath |
| conntrack near limit/insert failure | NAT/conntrack |

每次结论必须使用同一模板，不能只写故障分类：

```text
root cause:
supporting evidence:
exclusion evidence:
missing evidence:
confidence: high / medium / low
```

禁止只凭以下任一项下结论：no retrans 不能证明不是网络；pcap 没看到 request 不能证明 Client 未发送；future success 不能证明 Server 已收到；TCP ACK 不能证明 TLS/HTTP2/handler 已处理。缺失 pcap、event 或 delta 只有在 observation point、identity mapping、clock 和 collection health 都验证有效后，才能作为 absence evidence；否则写入 `missing evidence` 并降低 confidence。

## 十三、值班 Runbook

1. 取得 trace、stream、channel、connection、tuple 与 timeout stage；核对 `connection_generation` 和 netns。
2. 先检查 `manifest.json` 的 artifact status、index version/mapping age/candidates/fan-out result、effective pre-retention、freeze/protected status、privacy admission、clock、Tail Sampling completeness/loss 和 missing/partial artifacts。
3. 检查 A 时间线，找出第一个异常 gap；区分 acquire、EventLoop、write/future 与 response deadline。
4. 将 B 对齐到 socket、container netns/veth、CNI/overlay、sidecar 与 Node；确认 event-time index、EndpointSlice/service route、每一跳 tuple/NAT mapping 和所有 candidate Server fan-out 结果。
5. 将 C 对齐到 framework receive、queue、handler 和 response write；不要合并 receive→start queue delay 与 handler duration。
6. 比较同 Node、同 EventLoop、同 connection 的 sibling requests/streams，判断单请求、单 stream、连接或 Node 范围。
7. 只对仍未解释的时间段读取 Client/Server 双端 pcap；先确认观察点、drop 和 clock，再判断方向。
8. 按模板记录 supporting evidence、exclusion evidence、missing evidence 与 confidence；不得用单一正常 aggregate metric 排除网络。

## 十四、故障注入与验收

在隔离的 load-test 环境逐项注入以下故障，并为每项预先写出期望 A/B/C 与 collection-health signature：

1. EventLoop block。
2. Executor saturation。
3. Container CPU throttling。
4. Peer stop-read。
5. `tc netem` loss/latency/reorder。
6. Zero HTTP/2 stream window。
7. `RST_STREAM`/`GOAWAY`。
8. Sidecar reset/connect timeout。
9. CNI/overlay MTU issue。
10. Capture pipeline 主动制造 spans/events/packets loss。
11. 将 upstream SDK/agent 误配为 1–5% head sampling。
12. 注入 exporter/network delay，让 policy-relevant span 晚于 `decision_wait` 到达。
13. 制造 EndpointSlice/conntrack/sidecar mapping stale、ambiguous 与 fan-out timeout。

验收必须同时满足：

- 每种故障无需人工守候即可产生状态明确的 `complete|partial|unavailable|failure` incident bundle；
- timeout 后 2 分钟内完成 bundle，或在 bundle/告警中给出明确 failure reason；
- Trigger 时 application request snapshot 会立即 freeze；correlator 不等待 Trace，而是在 retention margin 内通过 event-time index fan-out 到 Client 与所有授权 candidate Server Nodes，Node closed T− evidence 随即 freeze/copy 或建立 protected refs；T～T+60 append 和 rotation close 后才 finalize，且原 ring 全程继续运行；
- VIP、NAT 与 service-mesh 路径测试能用 EndpointSlice/service route/CNI flow/conntrack/sidecar 的 versioned mapping 命中所有授权 candidates；stale/ambiguous/unresolved/timeout 会把 Server artifact 标为 partial/unavailable 并记录 candidates、version、mapping age 与 reason；
- 要声称完整 `T-60s` 前窗，实测 effective pre-retention 必须达到 60 秒加 propagation/pin/rotation margin；不足时自动标为 partial/unavailable，并准确列出缺失范围；
- 每种故障产生可区分的预期 signature，不以单个正常 aggregate metric 证明“不是网络”；
- packet ring 始终满足约 2 GiB/Node quota，且能看到 actual effective retention；
- trigger storm 下 `service/node/peer/normalized_cause` dedupe、每 Node 每小时最多 3 次 pin、降级顺序和业务磁盘安全水位均生效；exception/error text 与任意 event string 不进入 key/label；
- Tail Sampling pipeline 的 candidate traces 由 upstream `AlwaysOn`/`ParentBased(AlwaysOn)` 完整 export，1–5% 只在 Collector 最终保留 normal traces；同 Trace 路由、production `decision_wait`、policy error、early-drop/overflow 与 late ratio 都经过验证；
- Upstream head sampling misconfiguration 与 late-span 注入必须可见；`otelcol_processor_tail_sampling_sampling_late_span_age` 等实际版本指标进入 manifest，异常时 trace artifact 只能是 partial/unavailable，不得宣称 error/slow Trace 已保留；
- 只有 upstream complete export、same-trace routing、policy-relevant spans decision 前到齐且无 early drop/overflow/policy error 时，trace artifact 才可标 complete；所有 artifact status 只允许 `complete|partial|unavailable|failure`；
- OTel/log/eBPF/pcap 任一 collection loss 都可见并进入 manifest；
- Raw pcap 只在验证过的 TLS-encrypted allowlisted hop 出现；cleartext/TLS termination 后 hop 没有 raw artifact，改用丢弃 payload 的 metadata-only 证据；admission 会销毁不合规 artifact 并记录 failure；
- Evidence schema fuzz test 会拒绝并计数 free-form message、URL/query、headers、body、`db.statement`、payload fragment 与 invalid/unmapped values，且任何 artifact 都不出现被拒 value；
- bundle 绝不包含 body、token、cookie、`Authorization`、TLS session keys、secret 或所谓已脱敏片段；
- 值班人员可在 10 分钟内把故障归类到 Client 应用、container/Node datapath、TCP/network、Server 应用或 HTTP/2 stream，并给出 confidence。

## 十五、命令速查

这些命令只用于读取已经锁定的 observation point；不要在 timeout 后才临时启动采集，也不要用命令输出替代 identity/clock/collection-health 校验。

```bash
ss -tinm dst 192.0.2.10:443
sudo /usr/share/bcc/tools/tcpretrans -T
sudo /usr/share/bcc/tools/tcpdrop
sudo conntrack -S
docker inspect --format '{{.State.Pid}}' client
sudo nsenter -t 12345 -n ss -tinm
```

完整原理与参数见：[tcpdump/Wireshark 与 namespace 抓包](./01-tcpdump-wireshark.md)、[连接与 socket 排查](./02-connection-issues.md)、[丢包/延迟/eBPF 证据](./03-packet-loss-latency.md)、[Netty 性能边界](../04b-java-debugging/06-netty-performance.md)、[OpenTelemetry Tail Sampling](../03-observability/05-distributed-tracing.md#tail-based-sampling尾部采样)。
