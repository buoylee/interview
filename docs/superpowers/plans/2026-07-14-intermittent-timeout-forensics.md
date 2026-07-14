# Intermittent Timeout Forensics Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production Runbook that preserves bounded evidence for random request timeouts and distinguishes application concurrency, container networking, TCP/network, server processing, and HTTP/2 stream failures.

**Architecture:** Create one standalone evidence-timeline chapter under Stage 8, then add narrow backlinks from existing Netty, packet-loss, packet-capture, concurrency-saturation, and Stage 8 guide documents. The new chapter orchestrates existing primitives instead of duplicating their full explanations: A records Client request stages, B records kernel/TCP/container evidence, and C records Server receive/queue/handler stages.

**Tech Stack:** Markdown, Linux TCP/`TCP_INFO`, Docker network namespaces, Kubernetes/CNI, Netty, Prometheus/Grafana, OpenTelemetry Tail Sampling, eBPF/BCC, `dumpcap`/pcapng.

## Global Constraints

- Use `docs/superpowers/specs/2026-07-14-intermittent-timeout-forensics-design.md` as authoritative requirements.
- Baseline: Linux + Docker/Kubernetes + Java/Netty + Prometheus/Grafana + OpenTelemetry Collector + centralized logs.
- Documentation only: no runtime dependency, daemon, manifest, application code, or executable capture-agent implementation.
- Reuse existing Netty, Tail Sampling, TCP, and Wireshark chapters through links; do not duplicate full tutorials.
- Keep `trace_id`, `request_id`, `stream_id`, `channel_id`, connection generation, and 4-tuple out of Prometheus labels.
- Never claim one normal aggregate metric proves the network healthy; distinguish “no evidence” from “evidence of absence.”
- Packet default: snaplen 128, narrow host/port filter, 30-second or 100-MiB rotation, 20 files, about 2 GiB per Node.
- Incident default: T-60s through T+60s, 5-minute dedupe, 3 pins per Node per hour, TTL 3 days.
- Never capture body, token, cookie, Authorization header, or other secrets.
- Preserve unrelated working-tree changes in `cli-toolbox/10-remote-and-transfer.md` and `cs/0拷贝.md`.
- Use `apply_patch` for documentation edits.

---

## File Structure

| Path | Responsibility |
|---|---|
| `performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md` | New Runbook: identity, A/B/C timeline, containers, automated retention, decision matrix, validation, commands |
| `performance-tuning-roadmap/08-network-io/README.md` | Stage 8 discovery, completion criterion, artifact, common mistake |
| `performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md` | Netty-specific evidence; backlink to generic retention |
| `performance-tuning-roadmap/08-network-io/03-packet-loss-latency.md` | Packet-loss chapter; backlink and less absolute decision wording |
| `performance-tuning-roadmap/08-network-io/01-tcpdump-wireshark.md` | Capture mechanics; backlink to trigger/pin/quota |
| `performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md` | Concurrency tree; backlink to cross-layer Runbook |

---

### Task 1: Create the evidence-timeline and container-observability core

**Files:**
- Create: `performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md`
- Reference: `docs/superpowers/specs/2026-07-14-intermittent-timeout-forensics-design.md`
- Reference: `performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md:469`
- Reference: `metrics-decoder/04-network.md:20`

**Interfaces:**
- Consumes: Netty stage names `rpc_submit`, `eventloop_enter`, `transport_write`, `transport_flush`, `write_future_done`, `response_received | timeout`.
- Produces: stable sections for identity, Client A, transport/container B, Server C, Docker, Kubernetes, TLS, and HTTP/2.

- [ ] **Step 1: Verify the file is absent**

Run:

```bash
test ! -e performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md
```

Expected: exit `0`, no output.

- [ ] **Step 2: Create title, scope, and flight-recorder model**

Use `apply_patch`. Opening content must be:

```markdown
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
```

Add non-goals: no permanent full payload, no capture privilege in application containers, no single-metric network exclusion, no duplicate tutorials.

- [ ] **Step 3: Add request identity and clocks**

Add `## 二、先建立可关联的请求身份` containing all fields:

```text
trace_id, request_id, HTTP/2 stream_id, channel_id,
connection generation, local IP:port, remote IP:port,
service/peer, pod UID/container ID, node, network namespace,
timeout stage/deadline, wall-clock event time, monotonic duration
```

State exactly:

1. High-cardinality identity belongs in logs/traces/incident metadata, never metrics labels.
2. In-process duration uses `System.nanoTime()` or equivalent monotonic clock.
3. Cross-Node correlation uses synchronized wall time; clock status/offset enters `manifest.json`.
4. Record application, pre-NAT, post-NAT, sidecar, and server-observed tuples separately.

- [ ] **Step 4: Add A/B/C stage boundaries**

Add:

```text
A Client:
t0 request submit
t1 connection/channel acquired
t2 EventLoop enter
t3 transport write
t4 write future complete
t5 response headers/complete | timeout

B transport:
userspace → socket send buffer → TCP/qdisc
→ container netns/veth → bridge/CNI/overlay
→ host NIC/network → peer kernel

C Server:
t6 framework/network receive
t7 handler queued
t8 handler start
t9 handler finish
t10 response write complete
```

For A: full-volume bounded metrics; normal traces 1–5%; slow/error/timeout traces 100%; one structured failure snapshot; stage events held in a bounded in-memory ring.

For B: record `socket state`, `Send-Q`, `wmem_queued`, `notsent`, `bytes_sent`, `bytes_acked`, `unacked`, `retrans`, `RTT`, `RTO`, `cwnd`. Prefer Netty native epoll `TCP_INFO` for a small known pool; use `ss -tinm` by local port as fallback. State that `ss` cannot identify an HTTP/2 stream.

For C: record executor active/max, queue/rejection, event-loop lag, DB/HTTP pool pending/acquire latency, lock wait, GC pause, CPU throttling. Separate framework receive from handler start.

- [ ] **Step 5: Add Docker and Kubernetes paths and metric mapping**

Add:

```text
Docker:
container cgroup → container netns eth0 → host veth
→ docker bridge/overlay → iptables/NAT/conntrack → host NIC

Kubernetes:
pod cgroup/netns → pod veth → CNI datapath
→ kube-proxy/IPVS/iptables 或 eBPF service translation
→ overlay/underlay → sidecar/Ingress → node NIC
```

Add this mapping:

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

State that exact names vary by runtime, cAdvisor, kernel, CNI, and proxy; verify actual `/metrics` output.

- [ ] **Step 6: Add HTTPS/TLS/HTTP2 boundaries**

Require these statements:

- TCP ACK proves peer kernel receipt, not TLS decode or handler execution.
- Encrypted pcap still shows TCP handshake, ACK, retransmission, RST, window, timing; not method/path/body without session keys.
- Record TLS termination and each service-mesh hop as separate connections.
- Persist `stream_id → channel_id/generation/4-tuple`.
- Inspect flow-control windows, `WINDOW_UPDATE`, `RST_STREAM`, `GOAWAY`.
- One failed stream with healthy siblings suggests stream/handler/deadline; many failed streams with Send-Q/retrans suggests connection/TCP.

- [ ] **Step 7: Validate and commit Task 1**

Run:

```bash
rg -n '^## (一|二|三|四|五|六|七)、|trace_id|connection generation|Docker:|Kubernetes:|container_cpu_cfs_throttled|conntrack|RST_STREAM|GOAWAY' performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md
git diff --check -- performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md
```

Expected: headings 一 through 七 and all named signals appear; diff check exits `0`.

Commit:

```bash
git add performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md
git commit -m "docs(perf): add timeout evidence model"
```

---

### Task 2: Add unattended retention, guardrails, and operator workflow

**Files:**
- Modify: `performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md`
- Reference: `performance-tuning-roadmap/03-observability/05-distributed-tracing.md:141`
- Reference: `performance-tuning-roadmap/08-network-io/01-tcpdump-wireshark.md:101`

**Interfaces:**
- Consumes: A/B/C stages and identity keys from Task 1.
- Produces: bounded rings, trigger schema, incident bundle, decision matrix, duty Runbook, failure handling, and acceptance criteria.

- [ ] **Step 1: Add three bounded rings and packet command**

Add a table:

| Ring | Content | Location | Default |
|---|---|---|---|
| Request | A/C stage events | process memory | recent 30–60s per active connection |
| TCP | `TCP_INFO` samples | process/Node agent | recent 30–60s |
| Packet | headers | dedicated Node volume | bounded by duration, size, count, quota |

Use this documentation example:

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

Explain that `192.0.2.10` is a documentation address, capacity is about 2 GiB/Node, size rotation may shorten time retention, effective retention must be monitored, and dual-end rings are needed for directionality.

- [ ] **Step 2: Add Tail Sampling and trigger schema**

Add this complete Collector example:

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

Mark memory and trace-capacity values as load-test-sized examples, not universal production values. Policy semantics remain mandatory: errors and slow requests retained, normal requests sampled.

Trigger fields must be:

```text
event_time, service, peer, node, pod_uid/container_id,
network_namespace, trace_id, request_id, stream_id,
channel_id, connection_generation, local_tuple, remote_tuple,
timeout_stage, deadline
```

State: application emits event only; privileged Node agent owns eBPF/pcap; filters come from static allowlist, never event input.

- [ ] **Step 3: Add trigger flow, bundle, and manifest**

Document:

```text
Client timeout → correlator dedupe → wait for T+60s
→ pin Client/Server T-60s～T+60s
→ merge A/B/C + eBPF + container metrics + pcap
→ upload bundle → ring continues
```

Bundle must contain `manifest.json`, Client timeout, Trace, Server events, TCP/eBPF, container metrics, Client pcap, Server pcap. Manifest must record clock status, observation points/tuples, TLS termination, filter/snaplen/tool versions, pcap drops, eBPF loss, OTel/log drops, and missing artifacts with failure reasons.

- [ ] **Step 4: Add capacity, overload, security, and self-monitoring**

Document exact defaults from Global Constraints. Overload order:

1. Keep timeout metrics/logs.
2. Keep error/slow traces.
3. Aggregate eBPF if needed.
4. Pin only first/representative pcap.
5. Drop normal traces first.
6. Stop pinning before business disk safety margin.

Self-monitor: OTel received/dropped, Tail Sampling decision/memory, log exporter queue/drop, eBPF lost events, pcap received/dropped, agent health, ring disk, oldest timestamp/effective retention, trigger counts, pin result/latency, upload failures.

Security: no body/secrets; RBAC, audit, encryption, TTL, minimum privilege, static filter allowlist.

- [ ] **Step 5: Add decision matrix**

Include every mapping:

| Signature | Boundary |
|---|---|
| `t1-t0` high + EventLoop lag high | Client queue/EventLoop |
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

Add conclusion fields: root cause, supporting evidence, exclusion evidence, missing evidence, confidence high/medium/low. Forbid conclusions based solely on no retrans, missing pcap request, future success, or TCP ACK.

- [ ] **Step 6: Add duty Runbook, fault injection, acceptance, and command appendix**

Duty order:

1. Get trace/stream/channel/connection/tuple/timeout stage.
2. Inspect manifest loss fields first.
3. Find first abnormal A gap.
4. Align B across socket/container/CNI/sidecar/Node.
5. Align C across receive/queue/handler/response.
6. Compare siblings on same Node/EventLoop/connection.
7. Read dual-end pcap only for unexplained interval.
8. Record evidence, missing evidence, confidence.

Fault injection: EventLoop block, executor saturation, CPU throttling, peer stop-read, `tc netem` loss/latency/reorder, zero HTTP/2 stream window, RST/GOAWAY, sidecar reset, CNI/MTU issue, capture-pipeline loss.

Acceptance: unattended bundle; completion or explicit failure within 2 minutes; distinct signatures; quota safety; trigger-storm safety; visible collection loss; no secrets; classification within 10 minutes.

Append these concise examples, then link full explanations to owning chapters:

```bash
ss -tinm dst 192.0.2.10:443
sudo /usr/share/bcc/tools/tcpretrans -T
sudo /usr/share/bcc/tools/tcpdrop
sudo conntrack -S
docker inspect --format '{{.State.Pid}}' client
sudo nsenter -t 12345 -n ss -tinm
```

- [ ] **Step 7: Validate and commit Task 2**

Run:

```bash
rg -n 'dumpcap|filesize:102400|memory_limiter|tail_sampling|T-60s|2 GiB|eBPF lost events|证据判定矩阵|故障注入|命令速查' performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md
git diff --check -- performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md
```

Expected: all controls appear; diff check exits `0`.

Commit:

```bash
git add performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md
git commit -m "docs(perf): add timeout capture runbook"
```

---

### Task 3: Integrate the Runbook into existing learning paths

**Files:**
- Modify: `performance-tuning-roadmap/08-network-io/README.md:9`
- Modify: `performance-tuning-roadmap/08-network-io/01-tcpdump-wireshark.md:101`
- Modify: `performance-tuning-roadmap/08-network-io/03-packet-loss-latency.md:341`
- Modify: `performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md:615`
- Modify: `performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md:195`

**Interfaces:**
- Consumes: completed `06-intermittent-timeout-forensics.md`.
- Produces: discoverable backlinks without duplicated implementation detail.

- [ ] **Step 1: Update Stage 8 README**

Add learning-order row:

```markdown
| 6 | [06-intermittent-timeout-forensics.md](./06-intermittent-timeout-forensics.md) | 随机 timeout 无值守取证、容器网络、自动 pin、证据判定 |
```

Add mainline step “如果故障随机出现，证据是否由 bounded ring 自动保留？”, completion bullet “为随机 timeout 设计 A/B/C 证据链”, artifact “不含敏感 payload 的 timeout incident bundle”, and common mistake “timeout 后才抓包 → bounded ring + automatic pin”.

- [ ] **Step 2: Update packet-capture and packet-loss chapters**

After tcpdump rotation template, add:

```markdown
> 轮转只解决磁盘不无限增长，不保证 timeout 证据不会在工程师回来前被覆盖。随机故障应使用 [无值守取证 Runbook](./06-intermittent-timeout-forensics.md)：timeout 自动 pin 前后时间窗，并配置 dedupe、quota、TTL 和采集丢包监控。
```

Before packet-loss summary, add:

```markdown
> 对随机 request timeout，`netstat`/`ss` 的事后快照只能提供当前或聚合状态，不能单独还原那次请求。需要长期保留 Client、TCP/容器、Server 三层短期历史时，使用 [随机请求超时无值守取证](./06-intermittent-timeout-forensics.md)。
```

Change absolute branches to:

```text
connect 慢 → 优先查 DNS/TCP/TLS/LB 路径
firstbyte 慢 → 查 Server queue/handler/下游，也保留回程与 proxy 证据
```

- [ ] **Step 3: Update Netty and concurrency chapters**

Add Netty subsection and renumber the existing fault-injection section from `9.7` to `9.8`:

```markdown
### 9.7 生产环境无值守保留

本节定义 Netty 专属阶段、Channel 和 EventLoop 证据。随机 timeout 的长期运行方式——Tail Sampling、eBPF 事件、Docker/Kubernetes 网络层、pcap ring 自动 pin、quota/TTL 和 incident bundle——统一见 [`08-network-io/06-intermittent-timeout-forensics.md`](../08-network-io/06-intermittent-timeout-forensics.md)，避免在业务 EventLoop 同步写大量诊断日志。
```

Add concurrency-tree reference:

```markdown
- ⑥ 的随机 timeout 若无法人工复现，使用 [无值守跨层取证 Runbook](../08-network-io/06-intermittent-timeout-forensics.md) 自动保留 Client、容器/TCP、Server 证据。
```

- [ ] **Step 4: Validate links, formatting, and commit**

Run:

```bash
test -f performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md
rg -n '06-intermittent-timeout-forensics.md' performance-tuning-roadmap/08-network-io/README.md performance-tuning-roadmap/08-network-io/01-tcpdump-wireshark.md performance-tuning-roadmap/08-network-io/03-packet-loss-latency.md performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md
git diff --check -- performance-tuning-roadmap/08-network-io/README.md performance-tuning-roadmap/08-network-io/01-tcpdump-wireshark.md performance-tuning-roadmap/08-network-io/03-packet-loss-latency.md performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md
```

Expected: all five files link to the Runbook; diff check exits `0`.

Commit:

```bash
git add performance-tuning-roadmap/08-network-io/README.md performance-tuning-roadmap/08-network-io/01-tcpdump-wireshark.md performance-tuning-roadmap/08-network-io/03-packet-loss-latency.md performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md
git commit -m "docs(perf): link timeout forensics runbook"
```

---

### Task 4: Final factual and coverage gate

**Files:**
- Review: `docs/superpowers/specs/2026-07-14-intermittent-timeout-forensics-design.md`
- Review: `performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md`
- Review: all Task 3 integration files

**Interfaces:**
- Consumes: finished Runbook and backlinks.
- Produces: complete spec coverage, no placeholders, valid local links, and no unsupported exclusion claims.

- [ ] **Step 1: Scan placeholders and coverage**

Run:

```bash
rg -n 'TBD|TODO|FIXME|待定|稍后补充|以后实现' performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md performance-tuning-roadmap/08-network-io/README.md performance-tuning-roadmap/08-network-io/01-tcpdump-wireshark.md performance-tuning-roadmap/08-network-io/03-packet-loss-latency.md performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md
```

Expected: exit `1`, no matches.

Run:

```bash
rg -n 'Client 应用层|Kernel、TCP|Server 应用层|Docker|Kubernetes|Tail Sampling|eBPF|dumpcap|incident bundle|取证系统|HTTP/2|conntrack|CPU throttling|故障注入|信心' performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md
```

Expected: every requirement appears.

- [ ] **Step 2: Review eight factual boundaries**

Read the full Runbook and confirm:

1. write future success is not peer receipt;
2. TCP ACK is not handler execution;
3. retransmission supports a TCP delivery problem but does not identify a physical link alone;
4. missing event plus collector drops means unavailable evidence, not healthy result;
5. `ss` is a connection snapshot, not request/stream tracing;
6. NAT/sidecar tuples differ by observation point;
7. pcap duration shrinks under size rotation;
8. application emits triggers but never performs privileged capture.

Fix any missing or contradictory sentence with `apply_patch`.

- [ ] **Step 3: Run final scope checks**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended docs from this plan changed; unrelated pre-existing modifications remain unstaged.

- [ ] **Step 4: Commit factual fixes only if needed**

If Step 2 changed files:

```bash
git add performance-tuning-roadmap/08-network-io/06-intermittent-timeout-forensics.md performance-tuning-roadmap/08-network-io/README.md performance-tuning-roadmap/08-network-io/01-tcpdump-wireshark.md performance-tuning-roadmap/08-network-io/03-packet-loss-latency.md performance-tuning-roadmap/04b-java-debugging/06-netty-performance.md performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md
git commit -m "docs(perf): tighten timeout forensics claims"
```

If nothing changed, do not create an empty commit.

- [ ] **Step 5: Record completion evidence**

Run:

```bash
git log -4 --oneline
git status --short
```

Expected: three base implementation commits appear, plus the optional factual-fix commit if Step 4 required edits; only the user's unrelated changes remain uncommitted.
