# 网络观测工具

网络问题在微服务架构中尤为突出。一个请求可能跨越多个服务、经过多层网络设备，任何一个环节的丢包、重传或延迟都会影响整体性能。本文介绍 Linux 下从连接状态到协议级统计的网络观测工具。

## ss -tnp — 连接状态查看

`ss`（Socket Statistics）是 `netstat` 的现代替代品，速度更快（直接读取内核 netlink 接口，不解析 /proc）。

```bash
$ ss -tnp
State    Recv-Q  Send-Q  Local Address:Port   Peer Address:Port   Process
ESTAB    0       0       10.0.0.1:8080        10.0.0.2:45678      users:(("java",pid=3421,fd=8))
ESTAB    0       36      10.0.0.1:8080        10.0.0.3:52341      users:(("java",pid=3421,fd=9))
ESTAB    0       0       10.0.0.1:54321       10.0.0.4:3306       users:(("java",pid=3421,fd=12))
LISTEN   0       128     *:8080               *:*                 users:(("java",pid=3421,fd=5))
ESTAB    0       0       10.0.0.1:54322       10.0.0.5:6379       users:(("java",pid=3421,fd=15))
TIME-WAIT 0      0       10.0.0.1:45678       10.0.0.6:8080
TIME-WAIT 0      0       10.0.0.1:45679       10.0.0.6:8080
```

参数含义：`-t` TCP、`-n` 不解析域名、`-p` 显示进程。

### 关键列解读

| 列 | 含义 | 关注点 |
|----|------|--------|
| **State** | 连接状态 | ESTAB/TIME-WAIT/CLOSE-WAIT 的分布 |
| **Recv-Q** | 接收队列中未被应用读取的字节数 | > 0 说明应用处理不过来 |
| **Send-Q** | 发送队列中未被确认的字节数 | > 0 说明对端接收慢或网络拥塞 |

**连接状态分布分析：**

```bash
# 按连接状态统计数量
$ ss -tan | awk '{print $1}' | sort | uniq -c | sort -rn
  12456 ESTAB
   3421 TIME-WAIT
    234 CLOSE-WAIT
    128 LISTEN
     45 SYN-SENT
      8 FIN-WAIT-2
```

| 状态 | 数量异常说明什么 |
|------|-----------------|
| **TIME-WAIT 过多** | 短连接太多，考虑用连接池或长连接 |
| **CLOSE-WAIT 过多** | 应用没有正确关闭连接（代码 bug） |
| **SYN-SENT 过多** | 连不上对端（对端宕机或防火墙拦截） |
| **ESTAB Recv-Q 持续 > 0** | 应用处理请求太慢 |

**CLOSE-WAIT 是最需要警惕的**。对端已经关闭连接（发了 FIN），但本地应用没有 close。这通常是忘记关闭连接的代码 bug，会导致文件描述符泄漏。

```bash
# 找出 CLOSE-WAIT 连接属于哪个进程
$ ss -tnp state close-wait
Recv-Q  Send-Q  Local Address:Port    Peer Address:Port   Process
0       0       10.0.0.1:45678        10.0.0.7:8080       users:(("python3",pid=4521,fd=23))
0       0       10.0.0.1:45679        10.0.0.7:8080       users:(("python3",pid=4521,fd=24))
```

## ss -s — Socket 统计摘要

```bash
$ ss -s
Total: 15234
TCP:   12456 (estab 8234, closed 2345, orphaned 123, timewait 1890)

Transport Total     IP        IPv6
RAW       2         1         1
UDP       45        23        22
TCP       10111     8234      1877
INET      10158     8258      1900
FRAG      0         0         0
```

快速了解系统整体的 Socket 使用情况。`orphaned`（孤儿连接）和 `timewait` 数量过大需要关注。

## tcpdump — 网络抓包

tcpdump 是网络问题排查的终极工具。当其他工具告诉你"有网络问题"但不知道具体原因时，抓包分析。

### 基本用法

```bash
# 抓取特定端口的流量
$ sudo tcpdump -i eth0 port 8080 -nn
10:45:01.123456 IP 10.0.0.2.45678 > 10.0.0.1.8080: Flags [S], seq 1234567890, win 65535
10:45:01.123567 IP 10.0.0.1.8080 > 10.0.0.2.45678: Flags [S.], seq 9876543210, ack 1234567891, win 65535
10:45:01.123789 IP 10.0.0.2.45678 > 10.0.0.1.8080: Flags [.], ack 1, win 65535
10:45:01.124000 IP 10.0.0.2.45678 > 10.0.0.1.8080: Flags [P.], seq 1:345, ack 1, win 65535
```

参数说明：`-i eth0` 指定网卡、`-nn` 不解析域名和端口名。

Flags 含义：`[S]` SYN、`[S.]` SYN-ACK、`[.]` ACK、`[P.]` PUSH+ACK、`[F.]` FIN+ACK、`[R]` RST

### 常用过滤表达式

```bash
# 抓取特定主机的流量
$ sudo tcpdump -i eth0 host 10.0.0.2

# 抓取特定端口范围
$ sudo tcpdump -i eth0 portrange 8080-8090

# 抓取 TCP SYN 包（新连接建立）
$ sudo tcpdump -i eth0 'tcp[tcpflags] & tcp-syn != 0'

# 抓取 TCP RST 包（连接异常重置）
$ sudo tcpdump -i eth0 'tcp[tcpflags] & tcp-rst != 0'

# 保存到文件（用 Wireshark 打开分析）
$ sudo tcpdump -i eth0 port 8080 -w capture.pcap -c 10000

# 只抓前 100 字节（减少磁盘占用，通常够看 Header）
$ sudo tcpdump -i eth0 port 8080 -s 100 -w capture.pcap
```

### 排查重传

```bash
# 抓取 TCP 重传包
$ sudo tcpdump -i eth0 'tcp[tcpflags] & tcp-syn == 0' and '(tcp[13] & 0x04 != 0 or tcp[13] & 0x10 != 0)' -nn | head

# 更简单的方式：用 ss 看重传统计
$ ss -ti dst 10.0.0.4:3306
State  Recv-Q  Send-Q  Local Address:Port  Peer Address:Port
ESTAB  0       0       10.0.0.1:54321      10.0.0.4:3306
     cubic wscale:7,7 rto:204 rtt:1.234/0.567 retrans:0/12 ...
```

`retrans:0/12` 表示当前无未确认的重传，但总共已重传 12 次。

## iftop — 实时流量监控

```bash
$ sudo iftop -i eth0
                    12.5Mb          25.0Mb          37.5Mb          50.0Mb
└───────────────┴───────────────┴───────────────┴───────────────┘
10.0.0.1              => 10.0.0.2                    12.3Mb  10.5Mb  8.9Mb
                      <=                              8.5Mb   7.2Mb  6.1Mb
10.0.0.1              => 10.0.0.4                     5.2Mb   4.8Mb  4.5Mb
                      <=                              3.1Mb   2.9Mb  2.7Mb
10.0.0.1              => 10.0.0.5                     1.2Mb   1.1Mb  1.0Mb
                      <=                              0.8Mb   0.7Mb  0.6Mb

TX:             cum:   234MB   peak:   45.2Mb  rates:  18.7Mb  16.4Mb  14.4Mb
RX:             cum:   178MB   peak:   32.1Mb  rates:  12.4Mb  10.8Mb   9.4Mb
TOTAL:          cum:   412MB   peak:   77.3Mb  rates:  31.1Mb  27.2Mb  23.8Mb
```

快速看到哪些连接在消耗最多的带宽。三列数字分别是最近 2 秒、10 秒、40 秒的平均速率。

## nload — 带宽利用率

```bash
$ nload eth0
Device eth0 [10.0.0.1] (1/1):
===============================================================
Incoming:
                        Curr: 12.34 MBit/s
                        Avg:  10.56 MBit/s
                        Min:   2.34 MBit/s
                        Max:  45.67 MBit/s
                        Ttl: 234.56 GByte
Outgoing:
                        Curr: 18.92 MBit/s
                        Avg:  15.23 MBit/s
                        Min:   3.45 MBit/s
                        Max:  52.34 MBit/s
                        Ttl: 345.67 GByte
```

最简单的带宽监控工具。如果网卡是 1Gbps，当前入方向 12.34 Mbps，利用率约 1.2%，远未饱和。

## ip -s link — 网卡统计

```bash
$ ip -s link show eth0
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DEFAULT qlen 1000
    link/ether 0c:42:a1:3d:5e:f1 brd ff:ff:ff:ff:ff:ff
    RX:  bytes   packets errors dropped  missed   mcast
         8.5G   12545621      0    1523       0       0
    TX:  bytes   packets errors dropped carrier collsns
         6.2G    9823456      0       0       0       0
```

| 字段 | 含义 | 关注点 |
|------|------|--------|
| **errors** | 错误数 | > 0 说明网卡或驱动有问题 |
| **dropped** | 丢弃数 | > 0 说明内核来不及处理（缓冲区溢出） |
| **missed** | 网卡硬件丢弃 | 网卡环形缓冲区太小 |

**RX dropped = 1523** 需要排查原因：

```bash
# 查看网卡环形缓冲区大小
$ ethtool -g eth0
Ring parameters for eth0:
Pre-set maximums:
RX:     4096
TX:     4096
Current hardware settings:
RX:     256    ← 当前只有 256，可以调大
TX:     256
```

```bash
# 调大环形缓冲区
$ sudo ethtool -G eth0 rx 4096 tx 4096
```

## ethtool -S — 网卡驱动级统计

```bash
$ ethtool -S eth0 | head -20
NIC statistics:
     rx_packets: 12545621
     tx_packets: 9823456
     rx_bytes: 8500000000
     tx_bytes: 6200000000
     rx_errors: 0
     tx_errors: 0
     rx_dropped: 0
     tx_dropped: 0
     rx_over_errors: 1523        ← 接收溢出
     rx_crc_errors: 0
     rx_frame_errors: 0
     tx_aborted_errors: 0
     tx_carrier_errors: 0
     rx_missed_errors: 0
     rx_queue_0_packets: 3456789
     rx_queue_1_packets: 3234567
     rx_queue_2_packets: 3012345
     rx_queue_3_packets: 2841920
```

驱动级统计比 `ip -s link` 更详细，可以看到每个队列的收发情况。如果某个 rx_queue 的包量远大于其他队列，说明 RSS（Receive Side Scaling）配置不均。

## /proc/net/snmp — 协议级统计

```bash
$ cat /proc/net/snmp | grep Tcp:
Tcp: RtoAlgorithm RtoMin RtoMax MaxConn ActiveOpens PassiveOpens AttemptFails EstabResets CurrEstab InSegs OutSegs RetransSegs InErrs OutRsts InCsumErrors
Tcp: 1 200 120000 -1 5234567 3456789 12345 8901 8234 892345678 945678901 234567 0 45678 0
```

### 计算 TCP 重传率

```bash
# 两次采样（间隔 10 秒）
$ cat /proc/net/snmp | grep Tcp | tail -1 | awk '{print "OutSegs="$11, "RetransSegs="$13}'
OutSegs=945678901 RetransSegs=234567

# 10 秒后
$ cat /proc/net/snmp | grep Tcp | tail -1 | awk '{print "OutSegs="$11, "RetransSegs="$13}'
OutSegs=945778901 RetransSegs=234667

# 计算
# 这 10 秒内发出的包: 945778901 - 945678901 = 100000
# 这 10 秒内重传的包: 234667 - 234567 = 100
# 重传率 = 100 / 100000 = 0.1%
```

**TCP 重传率参考**：
- < 0.01%：极好
- 0.01% - 0.1%：正常
- 0.1% - 1%：需要关注，可能有网络问题
- > 1%：严重，需要排查网络链路

高重传率会导致延迟增加，因为 TCP 重传的超时通常是 200ms 起步，指数退避。

## 排查流程总结

```
"网络可能有问题"
    │
    ├─ ss -s → 连接状态分布正常？
    │   │
    │   ├─ CLOSE-WAIT 多 → 应用代码 bug
    │   ├─ TIME-WAIT 多 → 短连接太多
    │   └─ 正常 → 继续
    │
    ├─ ip -s link → 有丢包/错误？
    │   │
    │   ├─ dropped 高 → ethtool -g 调大缓冲区
    │   ├─ errors 高 → 网卡/线缆问题
    │   └─ 正常 → 继续
    │
    ├─ /proc/net/snmp → TCP 重传率高？
    │   │
    │   ├─ 高 → tcpdump 抓包分析
    │   └─ 正常 → 继续
    │
    └─ nload / iftop → 带宽饱和？
        │
        ├─ 饱和 → 升级带宽或优化流量
        └─ 不饱和 → 网络可能不是瓶颈
```

## 小结

| 工具 | 用途 | 关键指标 | 速览命令 |
|------|------|----------|----------|
| ss -tnp | 连接状态 | Recv-Q/Send-Q/State | `ss -tnp` |
| ss -s | Socket 摘要 | estab/timewait/orphaned | `ss -s` |
| tcpdump | 抓包分析 | 重传/RST/延迟 | `sudo tcpdump -i eth0 port 8080` |
| iftop | 实时流量 | 每连接带宽 | `sudo iftop -i eth0` |
| nload | 带宽监控 | 入/出带宽 | `nload eth0` |
| ip -s link | 网卡统计 | errors/dropped | `ip -s link show eth0` |
| ethtool -S | 驱动统计 | 每队列统计 | `ethtool -S eth0` |
| /proc/net/snmp | 协议统计 | TCP 重传率 | `cat /proc/net/snmp` |

网络排查的核心思路：先看连接状态和丢包（ss + ip），再看重传（/proc/net/snmp），最后必要时抓包分析（tcpdump）。
