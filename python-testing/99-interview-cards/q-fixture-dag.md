# pytest 如何构建并执行 fixture DAG，包括 teardown？

## 30 秒回答

pytest 从 test item 的参数名开始，在目录可见的 conftest、测试模块和已注册 plugin 中做 request-time lookup，再递归解析 fixture 参数形成 DAG。它按依赖拓扑 setup、在同一 request/scope 内缓存，并按已成功取得资源的反向顺序 teardown。scope 表达谁能共享资源和何时释放；setup 失败时，只清理此前已成功 setup 或已登记 finalizer 的资源。

## 机制

fixture 名字不是普通 import。靠近测试的同名 fixture 可覆盖远端定义；高 scope 不能依赖低 scope，否则生命周期倒置并触发 `ScopeMismatch`。yield 前是资源取得，yield 后是 cleanup；若在 yield 前失败，本 fixture 的 yield 后代码未登记，不会运行。`addfinalizer` 一旦注册就会运行，所以必须在资源真正取得后再登记。async fixture 还要让 client、session、engine 和 task 的 event-loop ownership 一致。

## lab 生产案例

根 [`tests/conftest.py`](../lab/tests/conftest.py) 暴露 function-scoped `order_factory`，共享的是无状态构造能力，不是可变订单。integration 的 [`conftest.py`](../lab/tests/integration/conftest.py) 让 session-scope 容器/engine 与每次测试的 UoW 分层拥有资源；E2E fixture 则把 Postgres、应用 lifespan、HTTP client 和 provider 按嵌套生命周期关闭。

## 取舍／反例

把数据库 session 或业务对象提升为 session scope 可能减少 setup，却会共享事务 snapshot、失败状态或可变实体；在 `-n 2` 下，session fixture 还会变成每 worker 一份。合理做法是高 scope 共享容器、engine 或只读 factory，function scope 创建 transaction、namespace 和业务数据。autouse 只适合每个 item 都必须遵守的隔离政策，不适合隐藏昂贵基础设施。

## 追问

- 同一 fixture 在一个测试中被两个上游请求，会执行几次？
- setup 的第三个节点失败时，哪些 teardown 必须运行？
- yield fixture 与 `addfinalizer` 在部分初始化失败时有何差异？
- xdist 下“session scope”为什么不是全套件唯一实例？

## 证据链接

- 章节：[fixture DAG](../03-fixtures-and-parametrization.md#fixture-是按名字解析的依赖-dag)、[cache 与 teardown](../03-fixtures-and-parametrization.md#cachescope-mismatch-与-teardown)、[async loop scope](../08-async-concurrency-background.md#31-pytest-asyncio-的-strict-与-auto)
- Fixtures：[`tests/conftest.py`](../lab/tests/conftest.py)、[`tests/integration/conftest.py`](../lab/tests/integration/conftest.py)、[`tests/e2e/conftest.py`](../lab/tests/e2e/conftest.py)
- Tests：[`test_order_factory.py`](../lab/tests/unit/test_order_factory.py)、[fixture leak scenario](../lab/scenarios/fixture-leak/README.md)

[返回速答索引](README.md)
