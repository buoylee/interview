# 阶段 6b：Python 排查与调优实战学习指南

> 本阶段目标：能针对 Python 服务选择正确并发模型，排查 asyncio 阻塞、Web 框架配置和常见性能反模式。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-gil-concurrency-model.md](./01-gil-concurrency-model.md) | GIL、threading、multiprocessing、asyncio 选型 |
| 2 | [02-asyncio-debugging.md](./02-asyncio-debugging.md) | 事件循环阻塞、慢回调、忘记 await |
| 3 | [03-web-framework-tuning.md](./03-web-framework-tuning.md) | FastAPI、Django、Gunicorn、ASGI/WSGI |
| 4 | [04-python-antipatterns.md](./04-python-antipatterns.md) | 深拷贝、全局状态、dict/list 创建、C 扩展 |
| 5 | [05-python-case-studies.md](./05-python-case-studies.md) | 多场景完整排查案例 |

---

## 本阶段主线

Python 实战调优的关键是先选对模型：

```text
CPU 密集 → multiprocessing / C 扩展 / 向量化
I/O 密集 → asyncio / async client / 连接池
Web 服务慢 → worker 模型 + 依赖耗时 + Trace
内存涨 → 引用链 + 缓存 + 循环引用
```

---

## 最小完成标准

学完后应该能做到：

- 判断任务适合 threading、multiprocessing 还是 asyncio
- 用 asyncio debug 找到阻塞调用
- 解释 Gunicorn worker 模型差异
- 找出一次 Django/FastAPI N+1 或同步阻塞问题
- 用 benchmark 或压测验证优化效果

---

## 本阶段产物

建议留下：

- 一份并发模型选型说明
- 一份 asyncio 慢回调或阻塞排查记录
- 一份 Web worker 配置对比
- 一个 Python 反模式修复前后对比

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| async def 内部写阻塞调用 | 使用异步库或线程池隔离 |
| CPU 密集任务用 threading | 使用 multiprocessing 或 C 扩展 |
| worker 越多越好 | 结合 CPU、内存、连接数和任务类型压测 |
| 只看框架性能榜单 | 以自身业务和部署方式压测为准 |

---

## 下一阶段衔接

完成 6b 后，你已经具备 Python 主语言排查能力。后续进入阶段 7 学完整压测方法，或进入 8-10 学生产环境排查。

