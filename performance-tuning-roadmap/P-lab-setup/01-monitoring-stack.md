# 监控栈一键部署

> Prometheus + Grafana + Jaeger + Loki 全家桶，用 Docker Compose 一条命令拉起完整可观测性平台。

---

## 1. 为什么需要本地监控栈

性能调优的前提是**可观测**。没有指标、没有链路追踪、没有日志聚合，所有优化都是盲人摸象。本文搭建的监控栈覆盖可观测性三大支柱：

| 支柱 | 工具 | 职责 |
|------|------|------|
| Metrics（指标） | Prometheus + Grafana | 时序指标采集与可视化 |
| Traces（链路） | Jaeger | 分布式链路追踪 |
| Logs（日志） | Loki + Grafana | 日志聚合与查询 |

```
                    ┌─────────────┐
                    │   Grafana   │ :3000
                    │  Dashboard  │
                    └──┬──────┬───┘
                       │      │
              ┌────────┘      └────────┐
              ▼                        ▼
       ┌─────────────┐         ┌─────────────┐
       │ Prometheus   │         │    Loki     │
       │  :9090       │         │   :3100     │
       └──────┬──────┘         └──────┬──────┘
              │                        │
     scrape targets              push logs
              │                        │
       ┌──────┴──────┐         ┌──────┴──────┐
       │  App /metrics│         │  Promtail   │
       │  Node Exporter│        │   :9080     │
       │  cAdvisor    │         └─────────────┘
       └─────────────┘
                    ┌─────────────┐
                    │   Jaeger    │
                    │  :16686     │
                    └─────────────┘
```

---

## 2. 目录结构

```
monitoring-stack/
├── docker-compose.yml
├── prometheus/
│   └── prometheus.yml
├── loki/
│   └── loki-config.yml
├── promtail/
│   └── promtail-config.yml
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── datasources.yml
│       └── dashboards/
│           └── dashboards.yml
└── data/                  # 持久化数据目录 (git ignore)
    ├── prometheus/
    ├── grafana/
    └── loki/
```

---

## 3. 完整 docker-compose.yml

```yaml
version: "3.8"

networks:
  monitoring:
    driver: bridge

volumes:
  prometheus_data: {}
  grafana_data: {}
  loki_data: {}

services:
  # ============ Prometheus ============
  prometheus:
    image: prom/prometheus:v2.51.0
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--storage.tsdb.retention.time=15d"
      - "--web.enable-lifecycle"          # 支持 /-/reload 热加载
    networks:
      - monitoring

  # ============ Grafana ============
  grafana:
    image: grafana/grafana:10.4.0
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - prometheus
      - loki
      - jaeger
    networks:
      - monitoring

  # ============ Jaeger (All-in-One) ============
  jaeger:
    image: jaegertracing/all-in-one:1.55
    container_name: jaeger
    restart: unless-stopped
    ports:
      - "16686:16686"   # Jaeger UI
      - "14268:14268"   # HTTP Collector (直接上报)
      - "6831:6831/udp" # UDP Agent (Thrift compact)
      - "4317:4317"     # OTLP gRPC (OpenTelemetry)
      - "4318:4318"     # OTLP HTTP (OpenTelemetry)
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    networks:
      - monitoring

  # ============ Loki ============
  loki:
    image: grafana/loki:2.9.5
    container_name: loki
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - ./loki/loki-config.yml:/etc/loki/local-config.yaml:ro
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - monitoring

  # ============ Promtail (日志采集) ============
  promtail:
    image: grafana/promtail:2.9.5
    container_name: promtail
    restart: unless-stopped
    ports:
      - "9080:9080"
    volumes:
      - ./promtail/promtail-config.yml:/etc/promtail/config.yml:ro
      - /var/log:/var/log:ro                   # 采集宿主机日志
      - /var/run/docker.sock:/var/run/docker.sock:ro  # 采集 Docker 日志
    command: -config.file=/etc/promtail/config.yml
    depends_on:
      - loki
    networks:
      - monitoring

  # ============ Node Exporter (主机指标) ============
  node-exporter:
    image: prom/node-exporter:v1.7.0
    container_name: node-exporter
    restart: unless-stopped
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - "--path.procfs=/host/proc"
      - "--path.sysfs=/host/sys"
      - "--path.rootfs=/rootfs"
      - "--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)"
    networks:
      - monitoring

  # ============ cAdvisor (容器指标) ============
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.49.1
    container_name: cadvisor
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    networks:
      - monitoring
```

---

## 4. 配置文件

### 4.1 Prometheus 配置 (`prometheus/prometheus.yml`)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: "node-exporter"
    static_configs:
      - targets: ["node-exporter:9100"]

  - job_name: "cadvisor"
    static_configs:
      - targets: ["cadvisor:8080"]

  # 应用服务 (后续 PerfShop 会用到)
  - job_name: "perfshop-java"
    metrics_path: "/actuator/prometheus"
    static_configs:
      - targets: ["host.docker.internal:8081"]

  - job_name: "perfshop-go"
    static_configs:
      - targets: ["host.docker.internal:8082"]

  - job_name: "perfshop-python"
    static_configs:
      - targets: ["host.docker.internal:8083"]
```

### 4.2 Loki 配置 (`loki/loki-config.yml`)

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h   # 7天
```

### 4.3 Promtail 配置 (`promtail/promtail-config.yml`)

```yaml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ["__meta_docker_container_name"]
        target_label: "container"
      - source_labels: ["__meta_docker_container_log_stream"]
        target_label: "stream"
```

### 4.4 Grafana 数据源自动配置 (`grafana/provisioning/datasources/datasources.yml`)

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

---

## 5. 各组件端口与访问地址一览

| 组件 | 端口 | 访问地址 | 用途 |
|------|------|----------|------|
| Grafana | 3000 | http://localhost:3000 | 统一仪表盘（admin/admin123） |
| Prometheus | 9090 | http://localhost:9090 | 指标查询、Targets 状态查看 |
| Jaeger UI | 16686 | http://localhost:16686 | 链路追踪查询 |
| Loki | 3100 | http://localhost:3100/ready | 日志接收端（不直接访问，通过 Grafana） |
| Promtail | 9080 | http://localhost:9080/targets | 日志采集状态 |
| Node Exporter | 9100 | http://localhost:9100/metrics | 主机指标原始数据 |
| cAdvisor | 8080 | http://localhost:8080 | 容器资源监控 |

---

## 6. 一键启动与验证

```bash
# 创建目录结构
mkdir -p monitoring-stack/{prometheus,loki,promtail,grafana/provisioning/{datasources,dashboards}}

# 把上述配置文件放入对应目录后启动
cd monitoring-stack
docker compose up -d

# 查看所有容器状态
docker compose ps

# 验证 Prometheus targets
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | head -30

# 验证 Grafana 可访问
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/health
# 返回 200 即正常

# 验证 Jaeger
curl -s http://localhost:16686/ -o /dev/null -w "%{http_code}"

# 验证 Loki
curl -s http://localhost:3100/ready
# 返回 ready 即正常

# 停止所有服务
docker compose down

# 停止并清除数据卷（重新开始）
docker compose down -v
```

---

## 7. 数据持久化说明

上面的 `docker-compose.yml` 使用了 Docker Named Volume：

- `prometheus_data` -- Prometheus TSDB 数据，默认保留 15 天
- `grafana_data` -- Grafana 的 Dashboard、用户配置、SQLite 数据库
- `loki_data` -- Loki 的日志 chunk 和索引数据

**生产建议**：如果你希望在 `docker compose down` 后保留数据，不要加 `-v` 参数。如果想绑定到宿主机特定路径方便备份，把 Named Volume 改为 Bind Mount：

```yaml
volumes:
  - ./data/prometheus:/prometheus
  - ./data/grafana:/var/lib/grafana
  - ./data/loki:/loki
```

注意 Bind Mount 需要处理好文件权限，Grafana 容器以 UID 472 运行：

```bash
mkdir -p data/{prometheus,grafana,loki}
chown -R 472:472 data/grafana
chown -R 65534:65534 data/prometheus   # nobody 用户
```

---

## 8. 常见部署问题排查

### 问题 1：Prometheus target 状态为 DOWN

```
# 检查容器网络连通性
docker exec prometheus wget -qO- http://node-exporter:9100/metrics | head

# 如果目标在宿主机上运行，使用 host.docker.internal（macOS/Windows）
# Linux 需要添加 extra_hosts:
services:
  prometheus:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### 问题 2：Grafana 登录后 Prometheus 数据源报错

最常见原因是 URL 写成了 `localhost:9090`。在 Docker 网络中，应该用**服务名** `http://prometheus:9090`。已通过 provisioning 自动配置解决。

### 问题 3：Loki 报 `too many outstanding requests`

Loki 单机模式默认并发限制低，修改 `loki-config.yml`：

```yaml
limits_config:
  max_query_parallelism: 2
  max_outstanding_requests_per_tenant: 2048
```

### 问题 4：cAdvisor 在 macOS 上无法启动

cAdvisor 依赖 Linux cgroups，在 macOS 上无法直接运行。解决方案：

1. 如果用 Docker Desktop，它运行在 Linux VM 中，通常没问题
2. 如果报错，可以在 `docker-compose.yml` 中注释掉 cAdvisor，用 Docker 自带的 `docker stats` 替代

### 问题 5：端口冲突

```bash
# 找出占用端口的进程
lsof -i :3000
# 或修改 docker-compose.yml 中的端口映射，例如把 3000:3000 改为 3001:3000
```

### 问题 6：Prometheus 热加载配置

修改 `prometheus.yml` 后不需要重启容器：

```bash
curl -X POST http://localhost:9090/-/reload
```

前提是启动参数中已包含 `--web.enable-lifecycle`（上面的配置已启用）。

---

## 9. 下一步

监控栈就绪后，继续部署 [PerfShop Demo 服务](02-perfshop-demo.md)，让三语言应用的指标、链路、日志全部接入这套监控平台。
