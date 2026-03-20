# 09 — 系统层调优

## 目标

应用层已无更多优化空间时，知道 OS 层能做什么、边界在哪里，以及如何验证效果。

## 原则

> 先用监控和压测找到瓶颈，再调对应的参数。不要盲目调整内核参数。
> 每次只改一个参数，压测对比效果。

---

## 文件描述符（fd）限制

### 为什么重要

每个 TCP 连接、文件、Socket 都消耗 1 个 fd。高并发服务 fd 不够会报 `Too many open files`。

### 查看当前限制

```bash
ulimit -n                          # 当前 shell 的软限制
cat /proc/{pid}/limits             # 某进程的实际限制
cat /proc/sys/fs/file-max          # 系统全局上限
```

### 修改方式

```bash
# 临时（当前 shell）
ulimit -n 65535

# 永久（/etc/security/limits.conf）
*   soft  nofile  65535
*   hard  nofile  65535

# 系统全局上限
sysctl -w fs.file-max=1000000
# 写入 /etc/sysctl.conf 永久生效
```

### 容器环境

```yaml
# docker-compose.yml
services:
  app:
    ulimits:
      nofile:
        soft: 65535
        hard: 65535
```

---

## TCP 参数调优

### 全连接队列（Accept Queue）

```bash
# 查看
ss -lnt   # Recv-Q 是当前队列长度，Send-Q 是队列上限

# 问题：Recv-Q > 0 持续增长 = 服务端处理不过来
# 调整队列大小
sysctl -w net.core.somaxconn=65535       # 系统级上限
sysctl -w net.ipv4.tcp_max_syn_backlog=65535  # 半连接队列
```

应用层也要配：
```python
# uvicorn
uvicorn app:app --backlog 2048
```

### TIME_WAIT 优化

大量短连接场景（如 HTTP 短连接）会产生大量 `TIME_WAIT`，占用端口和 fd。

```bash
# 查看数量
ss -s | grep TIME-WAIT

# 允许 TIME_WAIT 端口复用（客户端有用，服务端意义不大）
sysctl -w net.ipv4.tcp_tw_reuse=1

# 快速回收（危险！NAT 环境下会导致连接错误，不推荐）
# sysctl -w net.ipv4.tcp_tw_recycle=1  # 已在 Linux 4.12 移除

# 根本解法：使用 HTTP keep-alive（复用连接，不产生 TIME_WAIT）
```

### 保持连接（Keep-Alive）

```bash
# TCP Keep-Alive（防止空闲连接被中间设备断开）
sysctl -w net.ipv4.tcp_keepalive_time=600    # 600秒无数据后开始探测
sysctl -w net.ipv4.tcp_keepalive_intvl=30    # 探测间隔
sysctl -w net.ipv4.tcp_keepalive_probes=3    # 3次未响应则断开
```

---

## 内存参数

### Swappiness（何时使用 Swap）

```bash
# 查看
cat /proc/sys/vm/swappiness  # 默认 60

# 服务器场景推荐设低（尽量不用 Swap）
sysctl -w vm.swappiness=10

# 数据库服务器可设为 0（完全禁用，但 OOM 风险）
```

### OOM Killer 策略

```bash
# 查看进程的 OOM 分数（0=不杀，-1000=永不杀）
cat /proc/{pid}/oom_score
cat /proc/{pid}/oom_score_adj

# 保护关键进程（如数据库）
echo -1000 > /proc/{pid}/oom_score_adj

# 查看是否发生过 OOM
dmesg | grep -i "oom\|killed process"
journalctl -k | grep -i oom
```

### 大页内存（HugePages）

适用于大内存占用服务（如 JVM、数据库），减少 TLB Miss。

```bash
# 配置 2MB 大页
sysctl -w vm.nr_hugepages=1024
# 程序需要显式申请（一般数据库自动用，Python 程序较少）
```

---

## CPU 亲和性（CPU Affinity）

将进程绑定到特定 CPU 核，减少缓存失效。

```bash
# 查看当前亲和性
taskset -p {pid}

# 绑定到 CPU 0 和 1
taskset -cp 0,1 {pid}

# 启动时绑定
taskset -c 0,1 uvicorn app:app
```

**NUMA 架构**（多路服务器）：

```bash
# 查看 NUMA 拓扑
numactl --hardware

# 在特定 NUMA 节点运行（减少跨节点内存访问）
numactl --cpunodebind=0 --membind=0 uvicorn app:app
```

---

## 容器环境特殊注意

### cgroup 限制的影响

```bash
# 容器内看到的是宿主机 CPU 数，但受 cgroup 限制
cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us    # 限额
cat /sys/fs/cgroup/cpu/cpu.cfs_period_us   # 周期
# quota/period = 实际可用 CPU 数

# 错误配置：workers = CPU数 × 2，但 CPU数 用了宿主机的核数
# 正确做法：用 nproc --all 或读取 cgroup 计算
```

```python
# Python 中正确获取容器可用 CPU 数
import os

def get_cpu_count():
    try:
        # cgroup v2
        with open('/sys/fs/cgroup/cpu.max') as f:
            quota, period = f.read().strip().split()
            if quota != 'max':
                return max(1, int(int(quota) / int(period)))
    except:
        pass
    return os.cpu_count()
```

---

## sysctl 常用参数速查

```bash
# 网络
net.core.somaxconn           # accept 队列上限
net.ipv4.tcp_max_syn_backlog # syn 队列上限
net.ipv4.tcp_tw_reuse        # TIME_WAIT 复用
net.ipv4.ip_local_port_range # 临时端口范围（默认 32768-60999）

# 内存
vm.swappiness                # swap 使用倾向
vm.dirty_ratio               # 脏页写回触发比例
vm.overcommit_memory         # 内存超额分配策略

# 文件
fs.file-max                  # 系统 fd 上限
fs.inotify.max_user_watches  # inotify 监控数量（node 项目常遇到）
```

### 验证调整效果的流程

```
1. 压测基准（记录 RPS / P99 / 错误率）
2. 修改一个参数
3. 重启服务（部分参数需要重启）
4. 同样场景压测
5. 对比指标
6. 如无效果，回滚
```

---

## 实践任务

- [ ] 查看 FastAPI 进程当前的 fd 使用量和上限
- [ ] 压测时用 `ss -s` 观察 TIME_WAIT 数量变化
- [ ] 在容器中验证 Python 读到的 CPU 数是宿主机还是容器限额
- [ ] 模拟 fd 耗尽场景（打开大量连接不关闭），观察错误

## 关键问题

1. 服务报 `Too many open files`，有哪些可能原因（fd 泄漏 vs 限制太低）？
2. `net.core.somaxconn` 和 `listen()` backlog 参数的关系？
3. 为什么容器内看到的 CPU 核数是 32 但实际只能用 2 核？
4. `vm.swappiness=0` 和 `vm.swappiness=1` 的区别？
