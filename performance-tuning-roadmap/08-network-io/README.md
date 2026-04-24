# 阶段 8：网络与 I/O 排查学习指南

> 本阶段目标：能从应用超时、连接异常、丢包、TLS 问题和磁盘 I/O 慢中定位证据，而不是只看应用日志。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [02-connection-issues.md](./02-connection-issues.md) | 连接超时、拒绝、TIME_WAIT、端口耗尽 |
| 2 | [01-tcpdump-wireshark.md](./01-tcpdump-wireshark.md) | 抓包过滤、TCP 时序、重传、RST |
| 3 | [03-packet-loss-latency.md](./03-packet-loss-latency.md) | 丢包、延迟、MTU、mtr/traceroute |
| 4 | [04-tls-debugging.md](./04-tls-debugging.md) | 证书链、SNI、cipher、TLS 握手性能 |
| 5 | [05-io-performance.md](./05-io-performance.md) | iowait、磁盘队列、NFS、Direct I/O |

---

## 本阶段主线

网络排查要同时看两端：

```text
客户端看到超时
→ 服务端是否收到连接？
→ TCP 是否建连成功？
→ 是否重传、RST、窗口缩小？
→ 应用是否已经处理？
→ 中间代理是否超时？
```

---

## 最小完成标准

学完后应该能做到：

- 用 `ss` 判断连接状态和端口耗尽风险
- 用 tcpdump 抓一次请求完整 TCP 包
- 在 Wireshark 中识别重传、RST、FIN
- 用 mtr/traceroute 判断延迟或丢包位置
- 用 openssl/curl 排查一个 TLS 证书或握手问题
- 用 iostat 判断磁盘 I/O 是否排队

---

## 本阶段产物

建议留下：

- 一份连接状态统计
- 一个 pcap 文件或包时序截图
- 一份 TLS 检查输出
- 一份 I/O 观察记录
- 一份“应用日志 + 网络证据”的对应关系

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 只在客户端抓包 | 关键问题需要双端抓包 |
| 看到 TIME_WAIT 就调参数 | 先检查连接复用 |
| 看到某跳丢包就认定故障 | 看后续跳是否持续丢包 |
| 浏览器能访问就认为证书没问题 | 用 openssl 验证完整证书链 |

---

## 下一阶段衔接

阶段 8 解决网络和 I/O 证据。阶段 9a、9b 会进入数据库和中间件，它们经常是网络延迟和应用超时的下游根因。

