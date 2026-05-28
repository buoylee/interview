# GIL 是什么 / 为什么 / 何时释放

## 一句话回答

GIL 是 CPython 解释器里的一把进程级全局锁，规则是**同一时刻同一进程内只有一个线程能执行 Python 字节码**。它存在是为了简化内存管理（引用计数无需逐对象加锁）和兼容 C 扩展。它在阻塞 I/O、sleep、等锁、C 扩展显式释放、以及纯计算每约 5ms 时会被释放。

## 三层论证

1. **锁住了什么**：字节码执行的「那支笔」。多线程做 CPU 密集会被串行化，吃不满多核；做 I/O 密集时因 I/O 会放笔，仍能并发提速。
2. **为什么有**：① 引用计数线程安全（否则每次计数增减都要加锁，单线程也变慢）；② 海量 C 扩展依赖它保证线程安全；③ 单线程不背锁开销、实现简单。是历史 + 工程权衡，不是 bug。
3. **何时释放**：阻塞 I/O（socket/文件）、`time.sleep`、等待锁、设计良好的 C 扩展计算（numpy）、纯 Python 计算时每 `sys.getswitchinterval()`（默认 5ms）强制检查一次。

## 证据链接

- 章节原理：[01-foundations-gil §3](../01-foundations-gil/README.md)
- 调优视角：[performance-tuning-roadmap/06b-python-debugging/01-gil-concurrency-model.md](../../performance-tuning-roadmap/06b-python-debugging/01-gil-concurrency-model.md)

## 易追问的延伸

- **Q: 有 GIL 还要加锁吗？** → 要。GIL 只保证单条字节码不被打断，`x += 1` 是「读-改-写」多条字节码，中间可能被切走丢更新，和 Java `i++` 非原子一个道理。
- **Q: GIL 能去掉吗？** → Python 3.13 起有实验性 free-threaded 模式（PEP 703）能去 GIL，但 2026 年仍不成熟：单线程有回退、C 扩展未普遍适配。面试提一句即可。
- **Q: 那 CPU 密集怎么办？** → multiprocessing 多进程（每进程独立 GIL）或下沉到会释放 GIL 的 C 扩展（numpy/Cython）。
- **Q: 为什么 numpy 计算不受 GIL 影响？** → numpy 在 C 层用 `Py_BEGIN_ALLOW_THREADS` 主动释放 GIL，计算期间别的线程能跑。
