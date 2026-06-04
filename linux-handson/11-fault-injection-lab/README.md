# 11 · 故障注入实验室(道场)⭐⭐ —— 补「大厂真实经验」

> 🧪 **环境**:`multipass shell linux-lab`,工具由 [`00-lab/provision.sh`](../00-lab/provision.sh) 装齐(`fio` / `tc-netem` / `toxiproxy` / `strace --inject`)。
> 🎯 **北极星**:**补足你缺的「大厂真实经验」。** [`07`](../07-troubleshooting-playbook/) 给你诊断的**心法**(那条路径);这里是**道场**——按需把真故障造出来,在真服务上一遍遍走那条路径,直到变成反射。

---

## 一、为什么单独有这个目录(07 vs 11)

| | 07 排查方法论 | 11 故障注入实验室 |
|---|---|---|
| 是什么 | **心法**:`现象→指标→假设→工具→定位→修复→验证→复盘` | **道场**:按需造真故障,反复走那条路径 |
| 怎么用 | 读一遍,内化路径 | 一再回来刷,练成反射 |
| 一句话 | 教你「**该敲什么**」 | 让你「敲到**不用想**」 |

> 心法读懂不等于会用。你现在「不踏实」,缺的不是现场——`stress-ng`/`netem`/`Toxiproxy` 随时给你造一个**真**现场(内核看到的数字和线上一模一样);缺的是**把它跑够遍数**。这个目录就是让你跑够遍数的地方。

---

## 二、「大厂真实经验」拆解 —— 这个道场能补多少

「真实经验」不是一坨,拆开看,各部分能不能在家补差得很远:

| 「经验」的成分 | 道场能补多少 | 用什么补 |
|---|---|---|
| **见过的故障形状(广度)** | ✅ 大半 | 会长大的**故障动物园**(§六),覆盖真实事故的常见种类 |
| **事故工作流的肌肉**(止血→定位→根因→复盘) | ✅ 几乎全部 | 每个场景都走**完整事故流程** + 跑完填一份[复盘](./postmortem-template.md) |
| **在真实系统上排查**(不是玩具脚本) | ✅ 能 | 场景架在**真软件**上(Redis / nginx / Postgres),用 Toxiproxy/netem 搞坏 |
| **压力下的识别速度** | ✅ 部分 | **盲测 + 计时 + [Wheel of Misfortune](./drills/wheel-of-misfortune.md)**(脚本 [`drills/blind-test.sh`](./drills/blind-test.sh)) |
| **继承的「战争故事」** | ⚠️ 借 | 把**公开复盘**映射到场景上,白嫖别人的惨案(§七) |
| 万台规模的分布式直觉 / 真 on-call 的压力 / 组织祖传知识 | ❌ 补不了 | ——(前两个靠读;最后一个面试也不考) |

> **结论:这个道场能补足「大厂排查经验」的 ~70–80%**——恰好是面试最常考、日常最常用的那部分。剩下的 20–30% 靠「读公开复盘」补一部分,剩下只有真 prod 给得了——而那部分**面试本来也不指望一个没大厂背景的人有**。

---

## 三、设计原则(决定了里面装什么)

1. **真软件,不是玩具。** 慢依赖场景就真的起一个 Redis 让你查,不是 `sleep` 脚本。你练的是「在生产级软件上排查」。
2. **故障动物园(广度优先)。** 不只 CPU/IO,要覆盖 fd 耗尽、连接池耗尽、慢依赖、重试风暴、OOM 误判、CLOSE_WAIT、级联失败……**广度本身就是「经验」里最可复制的部分。**
3. **走完整事故工作流,不只是「定位」。** 每个场景:**① 止血(先别根因)→ ② 定位 → ③ 根因 → ④ 验证 → ⑤ 复盘**。其中「先止血再根因」和「写复盘」是最被低估、却最可复制的大厂肌肉。
4. **盲测 + 压力。** 看着答案抄命令 ≠ 会。要练「被丢一台不知道哪坏的机器,自己决定先敲什么」(脚本 [`drills/blind-test.sh`](./drills/blind-test.sh) + [Wheel of Misfortune](./drills/wheel-of-misfortune.md))。
5. **借来的经验。** 每个场景挂一个**真实公开复盘**,你等于继承别的工程师最惨的那天。
6. **诚实的 gap,转成面试叙事。** 知道哪些补得了、哪些补不了,面试时就能把「没大厂背景」讲成「我在自建实验室复现过 X 并定位到 Y」——这比含糊的大厂战争故事更打动人。

---

## 四、工具全景:上手层 vs 认识层

**入场测试**(一个工具要「上手安装」,得同时满足):① 单机能跑(不依赖 k8s/云机队);② 教的是**诊断**技能而非**编排**技能;③ 开源 + 低安装成本。
过不了测试、但有面试价值的 → **不安装,只「认识」**(能聊就行)。

| 工具 / 平台 | 怎么处理 | 为什么 |
|---|---|---|
| stress-ng · fio · tc/netem · Toxiproxy · strace --inject | **上手层(核心)** | 单机可跑、教诊断、开源低成本 |
| iptables/nftables(丢包/RST) | 上手层(轻量) | 内核自带,补「连接被重置」类场景 |
| **Chaos Mesh / LitmusChaos** | 认识层(谈资) | 要 k8s 集群;它们的 stress/network/io 实验**底层就是 stress-ng / netem / fault-injection**——你练 primitive 就学到实质,只是省掉 k8s 编排层 |
| **Chaos Monkey / Simian Army** | 认识层(历史+哲学) | 绑 AWS+Spinnaker、机队规模随机杀实例,单机复现无意义;但它是混沌工程鼻祖,「Principles of Chaos Engineering」必聊 |
| Chaos Toolkit | 认识层(可选上手) | Python 声明式实验,对转 Python 友好;但也是**编排器**,先掌握 primitive 再说 |
| Gremlin | 只提一句 | 商用 SaaS,违背「开源优先」+ 学习无需依赖商用 |
| PowerfulSeal / kube-monkey | 不单列 | k8s pod killer,归进「k8s 混沌平台」一句带过 |
| **Pumba** | 缓 → 接 [`09 容器`](../09-containers-from-linux/) | 单机 Docker 混沌,等做容器章再接 |
| 内核 fault-injection · dm-flakey/dm-dust | 缓 → 进阶可选 | 很「硬核真实」但要特定内核配置,payoff 偏「测错误路径」而非「诊断慢机器」 |
| libfiu / fiu-run | 不要(冗余) | 和 `strace --inject` 重叠,后者零安装 |
| Comcast | 不要(冗余) | 只是 tc/netem 的包装,直接学 tc/netem 更通用 |
| Prometheus / Grafana 等监控栈 | 不要(越界) | 那是 **observability**,归 `performance-tuning-roadmap/03-observability`;本道场专注「用自带工具当场诊断」 |

> 💡 **让你安心的事实**:那些集群级混沌平台,大多只是把这些 primitive 做了**编排封装**。你直接在一台机器上练 primitive,学到的是实质,跳过的只是「k8s 编排」这一层——那是另一项、可延后的技能。**你没漏掉肉,只是没先学摆盘。**

---

## 五、怎么用这个道场

每个场景按这个流程跑(别跳「复盘」那步,那才是大厂肌肉):

```
① 先建基线   在闲置 VM 上 uptime/vmstat/iostat/free/ss,记下 normal 长什么样(没基线就没异常,接 07 §2.5)
② 布置现场   按场景的「布置现场」跑注入命令(或用盲测脚本 drills/blind-test.sh 随机注一个,你别看是哪个)
③ 走事故流程  止血 → 定位(套 07 第一分钟清单 + 分层路径)→ 根因 → 验证
④ 填复盘     用 postmortem-template.md 写一份(逼自己复述因果链)
⑤ 翻揭晓     对答案、看「破案点」,错在哪记下来
⑥ 读公开复盘  看这题对应的真实世界事故,把「借来的经验」收进脑子
```

---

## 六、场景目录(故障动物园)

> 状态:✅ 已写 · 🚧 计划中(会持续长大)。每个场景一个文件,统一模板。

| # | 场景 | 资源/层 | 主要工具 | 对应的真实事故 | 状态 |
|---|------|---------|---------|---------------|------|
| 01 | CPU 饱和 | CPU | `stress-ng`,`top -H` | 死循环 / 频繁 Full GC / 算法退化 | [✅](./scenarios/01-cpu-saturation.md) |
| 02 | I/O 过载 | 磁盘 | `stress-ng --hdd` / `fio`,`iostat` | 慢盘 / 日志狂写 / NFS | [✅](./scenarios/02-io-overload.md) |
| 03 | fd 耗尽 | 文件 | 泄漏脚本,`lsof`,`/proc` | `Too many open files` | [✅](./scenarios/03-fd-exhaustion.md) |
| **04** | **慢依赖(下游变慢拖垮你)** | 网络/应用 | `Toxiproxy`,`strace`,`ss` | 跨 AZ / 慢查询 / sidecar 故障 | [✅](./scenarios/04-slow-dependency.md) |
| 05 | 连接池耗尽 | 应用 | `Toxiproxy`,`ss` | 下游慢 → 池占满 → 雪崩 | [✅](./scenarios/05-connection-pool-starvation.md) |
| 06 | OOM vs page cache | 内存 | `stress-ng --vm`,`free`,`dmesg` | 误判「内存泄漏」 | [✅](./scenarios/06-oom-vs-pagecache.md) |
| 07 | 重试风暴 / 惊群 | 网络 | `tc-netem`,`ss` | retry storm 雪崩 | [✅](./scenarios/07-retry-storm.md) |
| 08 | 磁盘写满 / inode 耗尽 | 磁盘 | `fallocate`,`df -i` | `No space left on device` | [✅](./scenarios/08-disk-full-inode.md) |
| 09 | CLOSE_WAIT 堆积 | 网络 | `ss`,`lsof` | 连接没关 | [✅](./scenarios/09-close-wait-pileup.md) |
| 10 | 级联失败(亚稳态) | 多层 | `Toxiproxy`+`netem` | 慢依赖 + 重试放大 → 雪崩 | [✅](./scenarios/10-cascading-failure.md) |

---

## 七、复盘与「借来的经验」

- **复盘模板**:[`postmortem-template.md`](./postmortem-template.md) —— 每跑完一个场景填一份。写复盘本身就是大厂核心技能(blameless postmortem)。
- **借来的经验**:[`borrowed-experience.md`](./borrowed-experience.md) —— 公开复盘阅读轨,把真实事故映射到上面的场景。先收藏这几个源:
  - GitHub **`danluu/post-mortems`**(经典合集)
  - **GitLab 公开复盘**、**Cloudflare / AWS / GCP** 事故博客
  - **k8s.af**(k8s 翻车故事集)
  - 论文/读物:Richard Cook《How Complex Systems Fail》、《Metastable Failures in Distributed Systems》(HotOS 2021)

---

## 八、进阶 / 未来(暂不进当前 scope,挂个钩)

- **k8s 混沌**:等核心单机道场稳了,加一个进阶附录——`kind`/`minikube` + Chaos Mesh 跑一个 k8s 混沌实验,完整体验大厂那套编排。
- **内核级 / 磁盘级**:内核 fault-injection、`dm-flakey` 做一个「磁盘坏块 / I/O error」进阶场景。

---

📌 **专题方法篇**:[`抓「难复现」的故障:间歇 / 高负载才触发 / 日志刷太快`](./catching-intermittent-faults.md) —— 把间歇性故障在实验室变「必现」、用指标代替翻日志、触发式抓取「录像而非盯梢」。**经典 `strace` 抓现场只对「稳定卡死」有效;这篇专治那些抓不到现场的。**

➡️ 配套心法见 [`07 · 排查方法论与工具箱`](../07-troubleshooting-playbook/);各资源原理见 [`03`](../03-process-model/)–[`06`](../06-networking/)。先从旗舰场景 [`04 慢依赖`](./scenarios/04-slow-dependency.md) 上手。
