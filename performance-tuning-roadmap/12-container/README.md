# 阶段 12：容器与云原生性能学习指南

> 本阶段目标：理解服务跑在容器和 K8s 中时，CPU、内存、网络和观测方式会发生什么变化。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-cgroup-resource.md](./01-cgroup-resource.md) | cgroups、CPU quota、内存限制、OOMKilled |
| 2 | [03-container-monitoring.md](./03-container-monitoring.md) | cAdvisor、node-exporter、kube-state-metrics |
| 3 | [02-k8s-performance.md](./02-k8s-performance.md) | Request/Limit、QoS、HPA/VPA、调度策略 |
| 4 | [04-service-mesh-perf.md](./04-service-mesh-perf.md) | Sidecar 开销、Envoy、mTLS、何时不用 Mesh |

---

## 本阶段主线

容器环境排查先确认资源边界：

```text
服务慢或 OOM
→ 容器 limit/request 是多少？
→ 应用是否感知容器资源？
→ CPU 是否被 quota throttling？
→ 内存是应用泄漏还是 limit 太小？
→ Sidecar 或网络代理是否增加延迟？
```

---

## 最小完成标准

学完后应该能做到：

- 解释 cgroup CPU quota 和 CPU throttling
- 判断容器 OOMKilled 与 JVM OOM 的区别
- 设计一个合理的 Request/Limit 初始值
- 看懂 Pod QoS 类别
- 解释 Service Mesh 的延迟和资源开销来源

---

## 本阶段产物

建议留下：

- 一份容器资源限制实验记录
- 一份 JVM/Go/Python 在容器中的资源识别结果
- 一份 Kubernetes Request/Limit 建议
- 一份 Service Mesh 开销评估或是否启用说明

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 容器里 free 显示宿主机内存就相信它 | 以 cgroup 指标为准 |
| CPU limit 不会影响延迟 | throttling 会造成明显抖动 |
| Request/Limit 随便填 | 基于压测和历史使用画像设置 |
| 默认启用 Service Mesh | 先量化 sidecar 开销和收益 |

---

## 下一阶段衔接

阶段 12 解决运行环境约束。阶段 13 会把性能和稳定性纳入 SLO、容量规划、事故响应和复盘。

