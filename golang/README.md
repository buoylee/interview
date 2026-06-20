# Go 资深/架构师面试 master 教程 —— 给 Java/Go 后端的「内幕 + 取舍」主线

> 把 Go 当面试题系统过一遍，但主线是**「黑盒里发生什么」+「为什么这么设计」+「架构师怎么取舍」**——不是语法书。每条线都从 **Java（你的母语）** 切入，反链 **Python**，落到面试白板能画/能讲的深度。
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-senior-interview-master-design.md`
>
> Go 版本基线 **1.22+**；版本敏感点显式标注。

## 怎么用这个课

1. **按主线读**：每条主线一个子目录，自成体系。急用先挑 track，不必从头读到尾。
2. **每章固定 7 段**：核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结。底层内幕写在正文，`99-interview-cards/` 只做最后的背诵自检。
3. **双向桥**：每个机制锚两头——从 Java（线程/异常/泛型擦除/JMM）切入，反链 Python（含已建的 `python-concurrency`）。
4. **想答面试**：去各 track 的 `99-interview-cards/` 找卡，每张链回正文做证据。
5. **想跑代码**：片段标了 Go 版本，复制到 `main.go` 跑（`go run main.go`）。

## 主线地图

### A. 语言与运行时内核（黑盒内幕核心）

| 主线 | 章数 | 一句话 | 状态 |
|---|---|---|---|
| [`error-handling/`](error-handling/) | 6 | **error 是值**：三种风格 / `%w`·`Is`·`As` / panic·recover·defer / 错误设计 / 并发错误 ← 面试高频痛点 | ✅ 完整 |
| [`type-system/`](type-system/) | 6 | 接口底层（iface/eface/itab/动态派发）/ 方法集与接收者 / 嵌入组合 / typed nil 陷阱 | ✅ 完整 |
| [`data-structures/`](data-structures/) | 5 | slice 扩容别名 / map 内幕无序 / string·rune / 逃逸分析 / struct 对齐 | ✅ 完整 |
| [`generics/`](generics/) | 3 | 泛型基础 / GCShape stenciling 底层（非模板非擦除）/ 与接口取舍 | ✅ 完整 |

### B. 运行时与性能（已有成熟笔记，本课只链接复用）

| 主题 | 去哪看 |
|---|---|
| **并发**（GMP/抢占/netpoller/channel/sync/context/模式） | [`golang/concurrency/`](concurrency/) ✅ 完整 10 章 + 面试卡 |
| **GC 与内存管理**（三色标记/写屏障/GOGC/GOMEMLIMIT） | `performance-tuning-roadmap/05a-go-profiling/03-go-gc-runtime.md` |
| **性能工具**（pprof / trace / 逃逸 / race） | `performance-tuning-roadmap/05a-go-profiling/0{1,2,4}-*.md`、`05b-go-debugging/*` |

### C. 工程化与架构（架构师级）

| 主线 | 章数 | 一句话 | 状态 |
|---|---|---|---|
| [`engineering/`](engineering/) | 3 | modules/MVS/workspace / project layout·build tags·embed / 工具链 | ✅ 完整 |
| [`testing/`](testing/) | 3 | table-driven / mock·DI / benchmark·fuzzing·集成测试 | ✅ 完整 |
| [`design/`](design/) | 4 | 小接口·消费方定义 / 组合优于继承·DI / 函数式选项 / 并发安全 API | ⬜ 待建 |
| [`stdlib/`](stdlib/) | 4 | io 接口家族 / net/http / encoding·json / database/sql | ⬜ 待建 |
| [`service-design/`](service-design/) | 4 | 服务骨架·优雅关闭 / gRPC vs REST / 中间件横切 / 可观测性接入 | ⬜ 待建 |

合计约 38 章 + 9 套面试卡，增量交付。

## 进度地图

| 主线 | 状态 | 备注 |
|---|---|---|
| umbrella spec | ✅ | `docs/superpowers/specs/2026-06-20-go-senior-interview-master-design.md` |
| master 索引（本文件） | ✅ | 全图 + 进度 + B 层复用链接 |
| `concurrency/` | ✅ | 已有完整 10 章 + 5 张深题卡 |
| `error-handling/` | ✅ 完整 | 6 章 + 面试卡(速答表 + 5 张深题卡)全部完成 |
| `type-system/` | ✅ 完整 | 6 章 + 面试卡(速答表 + 5 张深题卡)全部完成 |
| `data-structures/` | ✅ 完整 | 5 章 + 面试卡(速答表 + 5 张深题卡)全部完成 |
| `generics/` | ✅ 完整 | 3 章 + 面试卡(速答表 + 3 张深题卡);**A 层语言内核收官** |
| `engineering/` | ✅ 完整 | 3 章 + 面试卡(速答表 + 4 张深题卡);**C 层开篇** |
| `testing/` | ✅ 完整 | 3 章 + 面试卡(速答表 + 3 张深题卡) |
| 其余 3 条主线(C 层) | ⬜ 待建 | 按顺序：design → stdlib → service-design |

## 关联已有笔记（复用不重复）

- `performance-tuning-roadmap/05a-go-profiling/` — Go GC / pprof / trace / 逃逸（B 层）
- `performance-tuning-roadmap/05b-go-debugging/` — goroutine 泄漏 / 调试实操
- `observability/` — 可观测性（service-design C5 链接）
- `java/` — Java 侧基础，做对标锚点
- `python-concurrency/` — Python 并发，反向对标锚点
- `system-design/`、`distr-tx/` — 分布式系统/事务（本课非目标，service-design 仅点到链接）

## 外部参考资料

> 从原 `collections.md` stub 收编。深挖底层时的好资源。

- [Go 语言设计与实现（draveness）](https://draveness.me/golang/) — runtime/数据结构/调度的中文内幕书
- [Go Questions（Go 问题集）](https://www.bookstack.cn/books/qcrao-Go-Questions) — 面试向底层问答
- [golangFamily 面试题合集 + 知识图谱](https://github.com/xiaobaiTech/golangFamily)
- [你不知道的 Go：unsafe.Pointer / uintptr 原理](https://www.cnblogs.com/sunsky303/p/11820500.html) — `uintptr` 做指针运算、`unsafe.Pointer` 任意可寻址指针转换
