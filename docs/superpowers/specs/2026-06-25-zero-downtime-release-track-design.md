# 零停机发布与实例生命周期(机制层)Track — 设计 spec

> 日期:2026-06-25
> 目标受众:资深工程师 / 架构师,面试 + 工作
> 落点:`distribution/zero-downtime-release/`(新建小 track,5 章 + README + lab)

---

## 1. 背景与缘起

起点是 `fastapi-ops/01` 里一个具体问题(`--graceful-timeout` / `Server.shutdown()` 何时触发),延伸出一个更大的反思:**仓库对「分布式/生产环境优雅停机的整个过程」讲得不系统**。

调研结论(grep + 覆盖图 agent 双重确认):

- **已有但分散**:app 层排空(`golang/service-design`、`fastapi-ops/01`)、策略层(`system-design/09` 蓝绿/金丝雀/滚动 + schema 迁移)、网关健康检查与 reload drain(`gateway/03,08`)、数据迁移 expand-contract(`python-data/07`)。
- **关键缺口(机制层)**:
  - `preStop` 钩子在**整个仓库零命中** —— 这是修复 endpoint 摘除 vs SIGTERM 竞态的招牌机制,架构师面试必问。
  - **优雅上线 / 预热**作为发布概念几乎空白(`优雅上线`/`graceful startup`/`minReadySeconds` 零命中;warmup 只在性能 track)。
  - **滚动编排机制旋钮**(maxSurge/maxUnavailable/PDB/minReadySeconds)只被点名、未讲机制。
  - **连接生命周期**(keep-alive 让"摘流量"失效、WS/gRPC/SSE 排空)在发布语境里缺席。
  - **VM/注册中心摘除**(Nacos/Eureka/Consul/Dubbo)无系统覆盖。

**只补"优雅下线"这一题不够**:它的直接邻居(优雅上线、滚动旋钮、连接生命周期)在仓库里是空的,面试官顺藤摸瓜就露馅。所以做成一个机制层小 track。

---

## 2. 定位与边界

- **定位**:坐在 `system-design/09`(策略层)**之上的机制层**——只讲"这些发布策略底层靠什么机制成立",指进各语言/工具深矿。
- **不做(防重写、防 scope 膨胀)**:
  - 不重写发布**策略**(蓝绿/金丝雀/滚动的定义与取舍)→ 回链 `system-design/09`、`cloud-native-landscape/06`。
  - 不重写 **app 层排空细节** → 回链 `fastapi-ops/01`、`golang/service-design`、`golang/stdlib/01`。
  - 不重写**数据迁移**策略 → 回链 `system-design/09`、`python-data/07`。
  - 不写 k8s 对象模型基础 → 回链 `cloud-native/`。
- **守约**:`框架对照要生态平衡`(默认云原生/语言无关,k8s + VM 双环境,Python/Go/Java 仅在真主流处对照);`指进深矿不重写`;`底层进正文`(机制写正文,问答只复习)。

---

## 3. 核心不变式 + 心智模型(README 的脊柱)

**唯一不变式:**

> **流量只能打到「已就绪(ready)AND 不在退场(not leaving)」的实例。**

整个 track 都是在「实例生命周期的两个危险时刻」维持这条不变式:

```
            ┌─────────────── 一个实例的一生 ───────────────┐
  创建 ─▶ 启动 ─▶ [危险①: 还没热就接流量] ─▶ ready ─▶ 服务中 ─▶ [危险②: 还在服务就被拿走] ─▶ drain ─▶ 终止
            └ 优雅上线(支柱2)防危险①        └ 优雅下线(支柱3)防危险② ┘
```

这条不变式被「fleet 滚动(支柱4)」放大、被「连接可能是长连接(支柱5)」复杂化、被「两版本并存时数据要兼容(支柱6,已有家)」约束。健康信号(支柱1)是两半共同依赖的神经系统。

---

## 4. 六支柱地图与覆盖现状

| # | 支柱(机制层) | 它回答的面试题 | 仓库现状 | 本 track |
|---|---|---|---|---|
| 1 | 健康信号:liveness/readiness/startup 三探针 | 探针有几种,失败分别会怎样? | 🟡 部分 | **ch01** |
| 2 | 优雅上线:readiness gating + 预热 + slow-start | 新实例怎么保证热了才接流量? | ❌ 空白 | **ch02** |
| 3 | 优雅下线:SIGTERM→排空→SIGKILL + preStop + 竞态 | Pod 删除到进程退出发生了什么?为什么还掉请求? | 🟡 app 层有,分布式竞态❌ | **ch03(深)** |
| 4 | 滚动编排机制旋钮:maxSurge/PDB/minReadySeconds | 零停机发布怎么编排?滚动时怎么不掉容量? | 🟡 策略有,旋钮❌ | **ch04** |
| 5 | 连接生命周期:keep-alive/长连接 drain | LB 摘了为什么旧连接还在打?长连接怎么断? | ❌ 空白 | **ch05** |
| 6 | 兼容变更:expand-contract/向后兼容/flag | 滚动期两版本并存,schema 怎么改? | ✅ 有家 | 仅回链 |

---

## 5. Track 结构与逐章内容规格

落点:`distribution/zero-downtime-release/`。章节用扁平 `NN-*.md`(对齐 `gateway/`、`cloud-native/`、`system-design/` 风格)。

### README.md
- 不变式 + 生命周期时间线图(§3)。
- 六支柱地图 + 覆盖现状表(§4),标清谁在本 track、谁指出去。
- 与 `system-design/09`(策略层)的关系:**本 track 是机制层,09 是策略层,正交互链**。
- 阅读顺序、受众、如何配合 lab。

### 01-health-signals.md 〔健康信号:三探针〕
必须讲清:
- 三探针语义与**失败→动作**:liveness 失败→**重启容器**;readiness 失败→**从 Service/Endpoints 摘掉(不重启)**;startup 失败→**门控前两者**(慢启动期间不让 liveness 误杀)。
- **谁消费**:kubelet(liveness/startup 在节点本地)vs Endpoints/kube-proxy/Ingress/LB(readiness 决定路由)vs service mesh。点破"readiness 是 app→流量层的唯一开关"。
- 经典坑:liveness 探 DB → 依赖抖动→**级联重启**;readiness 抖动→**流量摆动**;探针超时/阈值配置(failureThreshold/periodSeconds)与误判。
- VM 对照:LB 主动(定时探)vs 被动(连续失败摘除)健康检查;注册中心心跳/TTL(Nacos/Eureka/Consul)。
- 回链:`cloud-native/08`(probe 调试)、`gateway/03`(LB 健康检查)。

### 02-graceful-startup.md 〔优雅上线/入场〕
必须讲清:
- **核心命题**:进程起来 ≠ 能接流量。冷的东西:连接池未建、JIT/解释器未热、本地缓存空、下游连接未预建、依赖未就绪。
- 机制:① readiness 只在**真热**后才转 true(把预热挡在 readiness 之前);② **startup probe** 兜慢启动;③ LB **slow-start / 渐进权重**(新实例流量爬坡,不一上来均摊全量);④ **minReadySeconds**(刚 ready 别马上被下一批替换);⑤ 主动预热手段(自打自/预建连接池/缓存预载/JIT 触发)。
- **冷启动雪崩**:扩容/重启的新实例被均摊全量流量瞬间打挂(尤其连接池冷 + 下游慢);和限流/熔断的关系。
- VM 对照:注册中心**延迟注册**(等预热完再注册)、LB 权重渐进。
- 回链:`fastapi-ops/01` lifespan startup(A8)、性能 track 的 warmup/cold-start。

### 03-graceful-shutdown.md 〔优雅下线/退场 · 最深 · 配 lab〕
必须讲清(本 track 的重心):
- **时间线**:`kubectl delete`/`docker stop` 触发后,**两件事并发发生**:(a) Pod 标记 Terminating → Endpoints controller 广播摘除 → kube-proxy/Ingress/云 LB 各自更新;(b) 容器收 **SIGTERM**。
- **竞态(核心)**:(a) 是**最终一致**的多跳传播,有 lag;(b) 往往**先到**。于是 SIGTERM 来时流量还在路上 → app 关 socket → 新连接吃 **RST / 502 / connection reset**。
- **修复**:① **`preStop` sleep**(睡过传播窗口,让 SIGTERM 推迟到 endpoint 摘干净后才真正触发优雅关);② readiness 提前转 fail 加速摘除;③ **为什么单靠 readiness-fail 不够**(传播仍异步,preStop 才是兜底等待)。给出 preStop + terminationGracePeriodSeconds 的标准配方。
- **时间预算**:`terminationGracePeriodSeconds` = preStop 时长 + app 排空 + 关池余量;否则 grace 内没排完被 **SIGKILL 硬切**。
- **app 层排空**(简述 + 回链):停 accept(关监听 socket)→ 等在途 → 关池/flush;Python 见 `fastapi-ops/01`,Go 见 `golang/service-design` + `golang/stdlib/01`。
- **LB 连接排空**:云 LB target group **deregistration delay / draining**;开源 nginx 的被动摘除局限。
- **长连接**(指向 ch05 系统化,这里点到):keep-alive 让"摘流量"对已建立连接无效;WS/gRPC stream/SSE 需主动断 + 通知客户端重连。
- **异步排空**:MQ 消费者(停拉新消息 → 处理完手头 → **提交位点/ack** → 退,避免重复消费或丢);后台 job / 定时任务;长请求。
- **VM/裸机版**:`shutdown hook` 调注册中心**主动摘除**(Nacos/Eureka/Consul/Dubbo)+ 延迟 + LB drain;`systemd` `TimeoutStopSec` / `KillSignal`(回链 `linux-handson/08`、`fastapi-ops/01` Part B)。
- **踩坑框 + 面试卡**。
- **配 lab**(§6)。

### 04-rollout-orchestration.md 〔滚动编排机制〕
必须讲清:
- 策略层只回链 `system-design/09`(蓝绿/金丝雀/滚动**定义**);本章讲**机制旋钮**。
- `maxUnavailable` / `maxSurge`:滚动时的**容量底线 / 超额上限**怎么算(例:replicas=10, maxUnavailable=20% → 滚动期至少 8 个在服务);和"不掉容量"的关系。
- `minReadySeconds`:新 Pod ready 后稳定多久才算数(防抖动 Pod 被当好的)。
- **PodDisruptionBudget**:自愿中断(drain/升级)vs 非自愿(节点挂);PDB 如何在 `kubectl drain` 时**阻塞**以保最小存活;和支柱3的 drain 是两个层次(PDB=fleet 级准入,preStop=单 Pod 级排空)。
- **滚动时序如何串起 ch02+ch03**:新 Pod 走完(支柱2)上线 ready → 才摘老 Pod(支柱3)→ 逐批推进。一张时序图。
- rollback 机制;与 HPA / 配额的交互。
- VM 对照:分批滚动 + LB 权重切换 + 健康门禁。
- 回链:`system-design/09`、`cloud-native-landscape/06,11`。

### 05-connection-lifecycle.md 〔连接生命周期〕
必须讲清:
- **核心命题**:"摘流量"摘的是**新连接的分发**,对**已建立**的连接无效 —— keep-alive / 连接复用让旧连接继续打到正在退场的实例。
- **L4 vs L7 LB** 的 draining 差异(L4 看连接、L7 看请求)。
- 长连接优雅断:服务端发**连接级关闭信号** —— HTTP/1.1 `Connection: close`;HTTP/2 & gRPC **GOAWAY**;WS/SSE 主动 close + 客户端 **重连/backoff/抖动**。
- service mesh(Envoy)的 connection draining / `drain_time`。
- 把 ch03 里碰到的连接问题在这里收口成一个连接模型。
- 回链:`gateway/03,08`、`cloud-native-landscape/04`(mesh)。

---

## 6. Lab 规格

落点:`distribution/zero-downtime-release/lab/`(docker-compose,本机可跑)。

- **拓扑**:`nginx`(L7,upstream = 2× uvicorn)+ 2 个 FastAPI 副本;副本带 `/health/ready`(可运行期翻转)+ 一个慢端点(模拟在途请求)+ 优雅 lifespan。
- **脚本流程**:
  1. `while curl` 循环压着服务,持续统计 2xx / 502 / connection-reset。
  2. **反面**:`docker kill` 一个副本(或 shell-form CMD 不转发 SIGTERM)→ 数掉的请求。
  3. **正面**:走优雅模式(`/health/ready` 翻 false → 等 nginx 不再分发 → 排空在途 → 退)→ 看错误归零。
  4. 演示 **keep-alive 失效**:nginx 对后端开 keepalive 时,"摘"了仍复用旧连接打过去 → 对照说明 ch05。
- **诚实边界(必须写明)**:docker-compose 能真实复现 **app 排空竞态 + keep-alive 失效 + grace 价值**;但 **k8s endpoint 传播竞态 / preStop** 需要真集群。正文把机制讲透,lab 附一个**可选 kind 附录**(`lab/kind-appendix.md`)给想真跑 k8s 竞态的人,**不强制**、不作为主路径。
- 遵守 `reference_handson_lab_bash`:采集脚本用 `bash script.sh`,`docker exec` 显式给 stdin。

---

## 7. 交叉链接 / 不重写映射

| 主题 | 家(回链,不重写) |
|---|---|
| 发布策略(蓝绿/金丝雀/滚动定义、flag) | `system-design/09` |
| 渐进交付 / GitOps / canary 机制 | `cloud-native-landscape/06` |
| 弹性/PDB 上下文 / 成本 | `cloud-native-landscape/11` |
| App 排空 Python | `fastapi-ops/01` |
| App 排空 Go | `golang/service-design`、`golang/stdlib/01` |
| probe 调试 | `cloud-native/08` |
| systemd 优雅停 | `linux-handson/08` |
| 数据迁移 expand-contract | `system-design/09`、`python-data/07` |
| 网关健康/reload drain | `gateway/03,08` |
| service mesh drain | `cloud-native-landscape/04` |

---

## 8. 深度契约(每章统一格式)

- 机制写**正文**(引入概念时就讲底层),问答题只做**复习自检**,不承载新知识。
- 每章含:核心机制(正文)+ **踩坑框 ⚠️** + **面试卡(分人人会/资深/架构师)** + **k8s↔VM 双环境对照**。
- 多语言:Python/Go/Java 仅在真主流处对照,配等价物,不绑死单一栈。
- 能链接的绝不重写;每个回链点明"那边讲什么、为什么不在这重复"。

---

## 9. 收口处理

- 现有 `distribution/优雅下线.md`(13 行 stub)→ 内容吸收进 `03-graceful-shutdown.md`;原文件改成一行指针指向新 track(避免孤儿/重复)。

---

## 10. 验收标准(每章"做完"的定义)

- ch01:能让读者答出"三探针失败各自的动作 + 谁消费 readiness",并说清 liveness 探 DB 的坑。
- ch02:能答出"进程起来≠能接流量"的 5 个机制 + 冷启动雪崩成因。
- ch03:能从 `kubectl delete` **逐拍**讲到进程退出,点出**竞态**与 **preStop** 修复,且 lab 能跑出"丢→不丢"。
- ch04:能算 maxUnavailable/maxSurge 的容量底线,讲清 PDB 与 preStop 是两个层次。
- ch05:能解释"摘流量为何对已建立连接无效"+ GOAWAY/`Connection: close`/客户端重连。
- README:六支柱地图成立,与 `system-design/09` 边界清晰。

---

## 11. 构建顺序(增量交付)

1. README(立骨架 + 地图)
2. **ch03 优雅下线 + lab**(本题、最深,先交付价值)
3. ch01 健康信号(ch03 的前置依赖,补在后但逻辑在前)
4. ch02 优雅上线
5. ch04 滚动编排
6. ch05 连接生命周期
7. 收口 stub 指针

每章建完即可独立自学;按需逐章 review。

---

## 12. 暂不纳入(out of scope,留待以后)

- 发布策略的深度重写(归 `system-design/09`)。
- 完整 k8s kind lab 作为主路径(仅作可选附录)。
- 有状态服务(StatefulSet)/ 数据库主从切换的优雅迁移(可作为未来支柱7)。
- 灰度/影子流量的流量染色机制(归网关/mesh track)。
