# 第 8 章 · Debug Playbook(一):Pod 起不来

> 🔬 k8s debug **最高频的一类**:Pod 没能正常 Running。这章给一张张**排查决策树**——Pending / ImagePullBackOff / CrashLoopBackOff / OOMKilled / 探针失败。每张:**现象 → 第一刀 → 分支判根因 → 修复 → 预防**,而且**根因都扣回前面的原理章**(这就是 C+:懂原理才会查,不是背命令)。

---

## 通用第一刀:黄金三件套 🔬

任何 Pod 异常,先敲这三个:

```bash
kubectl get pod <pod> -o wide       # STATUS + RESTARTS + 在哪个节点
kubectl describe pod <pod>          # 看 Events(★ 90% 的答案在这)+ Last State
kubectl logs <pod> [--previous]     # 应用日志;--previous 看上次崩溃的
```
> **心法**:先 `describe` 看 **Events**(k8s 告诉你它卡在哪),再 `logs` 看**应用**说了什么。这对应 `03b` 的 reconcile 思想——**故障 = 现实没趋近期望,看卡在哪一步**。

---

## A · Pending(调度不上)🔬 → 回扣第 4 章调度

**现象**:一直 `Pending`,没分到节点。**第一刀**:`describe` 看 Events 里 `FailedScheduling` 的原因。

| Events 说 | 根因 | 修复 |
|---|---|---|
| Insufficient cpu/memory | 没节点满足 **requests**(第 4 章) | 降 requests / 加节点 / Cluster Autoscaler |
| didn't match node affinity/selector | 亲和/nodeSelector 没匹配 | 改亲和,或给节点打 label |
| had taint that pod didn't tolerate | 节点污点没容忍 | 加 toleration |
| pod has unbound PVC | 存储没绑(第 6 章) | 查 PVC / StorageClass |

**预防**:合理设 requests、监控节点资源水位。

---

## B · ImagePullBackOff / ErrImagePull 🔬 → 回扣 03a 运行时拉镜像

**现象**:拉不到镜像。**第一刀**:`describe` 看 Events 拉取错误。

| 错误 | 根因 | 修复 |
|---|---|---|
| not found / manifest unknown | 镜像名/tag 错 | 核对镜像名、用存在的 tag |
| 401/403 unauthorized | 私有仓库没配 `imagePullSecret` | 配 pull secret |
| timeout / no route | 节点连不上 registry | 查 registry 可达性 / 镜像加速 |

**预防**:CI 校验镜像存在、**用 sha 不用 latest**(回扣第 1 章)、配好 pull secret。

---

## C · CrashLoopBackOff(最高频)🔬

**现象**:容器起来又崩、**反复重启**(BackOff = 指数退避,回扣 L3 退避思想)。**第一刀**:`kubectl logs --previous`(看崩溃前输出)+ `describe` 看 **Last State + Exit Code**。

| 线索 | 根因 | 修复 |
|---|---|---|
| 日志报错(连不上 DB / 配置缺失) | 应用启动即失败 | 修配置/依赖(回扣第 7 章 ConfigMap/Secret) |
| **Exit 137 + Reason: OOMKilled** | 内存超 limit 被杀(见 D) | 调 limit / 查泄漏 |
| 启动慢被 liveness 杀 | 探针太激进(见 E) | 配 startupProbe |
| Secret/ConfigMap 挂载失败 | 引用了不存在的配置 | 修引用 |

**预防**:启动依赖检查、合理 limits、探针配对。

---

## D · OOMKilled 🔬 → 回扣第 4 章 limits + linux/09 cgroup

**现象**:`describe` 里 `Reason: OOMKilled`,Exit 137。
**根因**:容器内存超 `limit` → 内核 **cgroup OOM killer** 杀掉(底层见 `linux-handson/09`)。

**排查**:
- `kubectl top pod` / 监控看**实际用量 vs limit**。
- 是不是**内存泄漏**(用量持续涨)。
- **Java 锚点** 🔬:JVM 在容器里**默认可能看不到 cgroup 内存限制**,堆设太大 → 超 limit 被杀。要用 `-XX:MaxRAMPercentage` 或新版 JDK(感知 cgroup),**别在容器里用固定 `-Xmx` 拍脑袋**。

**修复**:调 limit / 修泄漏 / JVM 感知 cgroup。**预防**:压测定 limit、监控内存。

---

## E · 探针失败:liveness / readiness / startup 🔬

三种探针,**配错是 CrashLoop 和「Service 没流量」的隐藏根因**:

| 探针 | 失败后果 |
|---|---|
| **liveness** | **重启容器** → 配太激进 → CrashLoop |
| **readiness** | **不给流量**(从 Endpoints 摘除)→ **Pod Running 却收不到请求**(直通第 9 章 Service 没流量!) |
| **startup** | 慢启动保护;**没配它** → liveness 把还在启动的容器当死了杀 → CrashLoop |

**修复**:探针路径/超时/初始延迟配对;慢启动应用**一定配 startupProbe**。

---

## 本章小结

- **黄金三件套**:`describe`(看 Events)+ `logs --previous` + `get -o wide`;**describe 永远第一刀**。
- **Pending** = 资源/亲和/污点/PVC 不满足(第 4 章);**ImagePullBackOff** = 镜像名/认证/网络(03a);**CrashLoopBackOff** = 应用崩/OOM/探针,看 `logs --previous`。
- **OOMKilled(Exit 137)** = 超 limit(第 4 章 + cgroup);**Java 要让 JVM 感知 cgroup**。
- **探针**:liveness 失败→重启、**readiness 失败→没流量(直通第 9 章)**、慢启动要 startupProbe。
- 下一章:`09` 网络与节点 debug(Service 没流量 / DNS / 节点 NotReady)。

---

## 章末问答(复习自检)

1. Pod 异常的「黄金三件套」命令是什么?为什么 describe 优先?
2. Pending 的四类常见根因?各怎么修?
3. CrashLoopBackOff 你会先敲什么命令?为什么是 `--previous`?
4. Exit 137 是什么?Java 应用在容器里为什么容易 OOMKilled、怎么防?
5. readiness 探针失败,Pod 是什么状态、会发生什么?(为什么直通「Service 没流量」)
6. **综合题**:一个 Pod 反复 CrashLoopBackOff,给出你从 0 到定位根因的完整排查路径。
```
