# 阶段 P：实践环境搭建学习指南

> 本阶段目标：先拥有一个可以反复练习的环境。不要一开始理解所有组件配置，先保证服务能跑、指标能看、负载能打。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-monitoring-stack.md](./01-monitoring-stack.md) | 拉起 Prometheus、Grafana、Jaeger、Loki，确认可观测性入口可用 |
| 2 | [02-perfshop-demo.md](./02-perfshop-demo.md) | 理解 PerfShop 作为贯穿项目的角色，跑通至少一个服务和一个接口 |

---

## 最小完成标准

完成阶段 P 不等于搭出完整生产级监控平台。最小标准是：

- Grafana 可以打开
- Prometheus 可以访问
- 至少有一个服务暴露 metrics
- 至少有一个 HTTP 接口可以被 `curl` 调通
- 可以用 wrk、Locust 或 curl 循环制造稳定请求
- 能在 Grafana 或 Prometheus 中看到请求相关指标

如果当前 PerfShop 的完整三语言实现尚未就绪，可以先用任意一个已有 HTTP 服务替代。阶段 P 的核心不是“三语言完整”，而是“后续练习有可观测目标”。

---

## 推荐推进方式

### 第一步：只跑监控栈

先完成：

```bash
docker compose up -d
```

并确认：

- Prometheus health 正常
- Grafana 能登录
- Jaeger UI 能打开
- Loki ready 正常

这一步只验证基础设施，不接业务服务。

### 第二步：接入一个最小服务

优先接入一个服务，而不是一次接 Java、Go、Python 三个服务。

最小服务需要具备：

- `/health`
- `/metrics`
- 一个业务接口，例如 `/api/products`

只要这个服务能被 Prometheus 抓到指标，就可以进入后续阶段。

### 第三步：制造稳定负载

先用最简单方式确认请求能持续产生：

```bash
while true; do
  curl -s http://localhost:8080/health > /dev/null
  sleep 1
done
```

后续阶段 3.5 再正式使用 wrk 或 Locust。

---

## 本阶段产物

建议留下这些材料：

- 监控栈启动命令和容器状态
- Prometheus targets 截图或文字记录
- Grafana 数据源截图或配置记录
- 一个服务的 `/metrics` 输出片段
- 一个业务接口的 curl 输出

示例记录：

```text
阶段：P
服务：perfshop-java 或替代服务
健康检查：通过
Prometheus target：UP
Grafana：可访问
下一步：进入阶段 1，建立排查方法；进入阶段 3 时再完善 Dashboard
```

---

## 常见卡点

| 卡点 | 处理方式 |
|------|----------|
| 端口冲突 | 先改 Grafana 或 Prometheus 映射端口，不要停在这里 |
| Docker 镜像拉取慢 | 先使用本机已有服务替代业务服务，监控栈后补 |
| cAdvisor 在 macOS 上异常 | 暂时跳过 cAdvisor，不影响应用层学习 |
| Jaeger 没有 Trace | 阶段 P 只要求 UI 可用，Trace 接入放到阶段 3 |
| Loki 没有日志 | 阶段 P 只要求 ready，日志规范放到阶段 3 |

---

## 进入下一阶段前自检

- [ ] 我知道 Grafana、Prometheus、Jaeger、Loki 分别解决什么问题
- [ ] 我能打开至少一个监控 UI
- [ ] 我能让一个 HTTP 服务持续收到请求
- [ ] 我知道后续所有实操都会围绕“服务 + 负载 + 指标”展开

