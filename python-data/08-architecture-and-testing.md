# 08 · 架构权衡与测试:判断层收口

> **为什么这章重要**:前面七章是「机制」,这章是「判断」——把数据访问放进真实架构里要回答的取舍题:**要不要给数据层加抽象(repository)?领域模型和 ORM 实体该不该分?数据层怎么测才靠谱?** 这是从「会用 SQLAlchemy」到「能为一个团队定数据层方案」的最后一跃,也是面试里区分高级和资深的地方。
>
> **一句话心智**:抽象**按需**加(会换实现 / 要隔离领域才加,否则 YAGNI);数据层**用真 DB 测**(事务回滚 fixture),别 mock ORM。

## 一、要不要 repository?三个层次的取舍

「数据访问要不要包一层?」有三种常见姿势,从轻到重:

| 姿势 | 怎么做 | 适合 |
|---|---|---|
| **直接用 Session** | service / 路由里直接 `s.scalars(select(...))` | 中小项目、CRUD 为主——**多数项目的正解** |
| **repository** | `UserRepository.get(id)` 把查询收进一个类 | 领域复杂、查询要复用、想隔离持久化细节 |
| **active-record** | 实体自带 `User.find()`/`user.save()` | 极简脚手架(Django ORM 就是这味);耦合最紧 |

**别一上来就 repository**。它的价值在两点——**会换底层实现**(今天 Postgres 明天换别的,想让上层不动)、或**要把领域逻辑和持久化彻底隔开**(下一节)。如果你的「repository」只是把 `select(User).where(id==...)` 换个名字叫 `get`,那它没带来任何收益,只是多一层转发样板。**YAGNI**:等到查询开始重复、或领域确实需要隔离时再抽。

```python
# repository:只有当它真的封装了「非平凡的、会复用的」查询逻辑时才值
class OrderRepository:
    def __init__(self, session): self.s = session
    def pending_for_user(self, user_id: int) -> list[Order]:
        return self.s.scalars(
            select(Order).where(Order.user_id == user_id, Order.status == "pending")
        ).all()
    # 若只是 get(id)/add()/delete() 的转发,直接用 Session 就好,别包
```

## 二、领域模型 vs 持久化模型:该不该分

**ORM 实体不等于领域对象**。ORM 实体是「表的镜像」——字段对应列、带 Session 绑定、有懒加载;领域对象是「业务概念」——带行为、不该知道数据库存在。小项目里两者合一(实体直接当领域对象用)完全没问题,**也是默认**。

什么时候**拆开**(领域对象 + 单独的 ORM 模型 + 两者间的映射)?

- 领域逻辑复杂(DDD 那一套),你不想让「数据库的形状」污染领域模型(比如领域里一个聚合,在库里拆成三张表)。
- 想让领域层**完全不依赖** SQLAlchemy,能脱离数据库单测。

代价很实在:**多一层映射代码 + 维护成本**。所以这是**重型项目的选择**,不是默认动作。判断句:**「领域复杂到 ORM 实体撑不住业务表达」时才拆,否则合一**。又一次 YAGNI。

## 三、数据层怎么测:用真 DB,别 mock ORM

最常见的错误:为了「快」「纯单元」,把 Session / query 全 mock 掉。**这是反模式**——你测的全是「mock 有没有被调用」,而真正会出事的地方(SQL 对不对、约束、事务、N+1、迁移)一个都没覆盖。数据层的 bug 几乎都在「和真实数据库交互」处,mock 把它们全藏起来了。

**正解:对真实数据库(或同款容器)测。** 两种主力策略:

### ① 事务回滚 fixture(快)

每个测试包在一个事务里,**测完回滚**——数据库瞬间干净,不用每次重建数据。pytest fixture:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

@pytest.fixture
def session():
    engine = create_engine("postgresql+psycopg://.../test_db")
    conn = engine.connect()
    txn = conn.begin()                 # 外层事务
    s = Session(bind=conn)
    yield s                            # 测试在这个 session 里跑
    s.close()
    txn.rollback()                     # 测完整体回滚,库恢复原状
    conn.close()
```

快、隔离好;适合绝大多数数据层单测。局限:测「提交本身的行为」或跨事务可见性时,这个「永不提交」的包裹会碍事。

### ② testcontainers(贴生产)

用 [testcontainers](https://testcontainers.com/) 在测试里**真起一个 Postgres 容器**(就是你 lab 里那个 image),测完销毁。最贴近生产(真 Postgres 的类型、约束、并发行为),适合迁移测试、隔离级别测试、集成测试。代价:每次起容器慢一点。

**两者搭配**:大量数据层单测走 ①(快),少量「必须真提交 / 真并发 / 真迁移」的集成测试走 ②。

### ③ 把 N+1 写成断言(防回归)

第 [05](05-n-plus-one-and-query-perf.md) 章的计数器可以变成测试——**锁住「这个接口最多发 N 条 SQL」**,有人不小心引入懒加载循环时 CI 立刻红:

```python
def test_list_authors_is_not_n_plus_one(session):
    count = {"n": 0}
    from sqlalchemy import event
    event.listen(session.bind, "before_cursor_execute",
                 lambda *a: count.__setitem__("n", count["n"] + 1))
    load_authors_with_books(session)        # 被测的业务函数
    assert count["n"] <= 2, f"N+1 回归:发了 {count['n']} 条 SQL"
```

这是把性能契约**固化进测试**——比「上线后靠 APM 发现」早得多。

## 四、收口:全书的数据层决策表

把前八章的判断浓缩成一张「该用什么」的速查:

| 问题 | 默认 | 升级到…的信号 |
|---|---|---|
| 用 ORM 还是 Core/raw? | ORM(对象写操作) | 报表/聚合/批量 → Core/raw([00](00-mindset-and-selection.md)/[05](05-n-plus-one-and-query-perf.md)) |
| sync 还是 async? | sync(psycopg) | 海量并发 + 全异步栈 → async([06](06-async-data-access.md)) |
| 加载策略? | 显式 eager(selectinload) | 多对一/一对一 → joinedload([05](05-n-plus-one-and-query-perf.md)) |
| 事务边界? | session-per-request | 局部回滚 → savepoint([04](04-transactions.md)) |
| 隔离级别? | READ COMMITTED | 读后写防丢更新 → 乐观锁 / SERIALIZABLE+重试([04](04-transactions.md)) |
| 要 repository 吗? | 直接用 Session | 查询复用 / 隔离领域才包(本章) |
| 领域/持久化分开吗? | 合一 | 领域复杂到实体撑不住才拆(本章) |
| 怎么测? | 真 DB + 事务回滚 fixture | 真提交/并发/迁移 → testcontainers(本章) |

贯穿全表的就两条原则:**抽象按需(YAGNI)、测试对真 DB**。

## Java/Go 对照框

| 关注点 | Java(Spring) | Go | Python |
|---|---|---|---|
| repository | Spring Data `Repository`(接口即实现) | 手写 interface + 实现 | 手写类 / 直接 Session |
| 领域/持久化分离 | JPA 实体 vs DDD 领域对象 | 普遍分(struct 解耦) | 按需,默认合一 |
| 数据层测试 | `@DataJpaTest` + H2/Testcontainers | testcontainers-go / sqlmock | 事务回滚 fixture / testcontainers |
| mock DB | 有 sqlmock 派,但社区倾向真 DB | sqlmock vs testcontainers 之争 | **倾向真 DB,别 mock ORM** |

差异:Spring Data 的 repository 是「定义接口、框架生成实现」,几乎零成本,所以 Java 项目默认就有 repository 层;Python 没有这种自动生成,手写 repository 是实打实的样板,因此**「要不要 repository」在 Python 里是个真问题**,默认直接用 Session 反而更务实。测试哲学两边趋同:**能用真数据库就别 mock**。

## 章末面试卡

**Q1. 数据访问要不要加 repository 层?**
按需。默认直接用 Session(中小项目/CRUD 的正解);只有当查询逻辑要复用、或要把持久化细节和领域隔开、或预期会换底层实现时才包。若 repository 只是给 `select(...)` 换个名字转发,纯属样板,YAGNI。

**Q2. 领域模型和 ORM 实体该不该分开?**
默认合一(实体直接当领域对象,小项目够用)。只有领域逻辑复杂到「数据库的形状会污染领域表达」、或要让领域层完全脱离 SQLAlchemy 单测时,才拆成领域对象 + ORM 模型 + 映射——代价是多一层映射维护成本。又一次 YAGNI。

**Q3. 数据层应该怎么测?为什么不该 mock ORM?**
对真实数据库测。mock 掉 Session/query 只能验证「mock 被调用」,而数据层真正的 bug(SQL 正确性、约束、事务、N+1、迁移)全在与真实 DB 交互处,mock 把它们全藏了。用事务回滚 fixture(快、测完 rollback)做大量单测,用 testcontainers(真起 Postgres)做必须真提交/并发/迁移的集成测试。

**Q4. 怎么在测试里挡住 N+1 回归?**
用 `before_cursor_execute` 监听器数本次业务发了多少条 SQL,断言 `count <= 阈值`。有人引入懒加载循环导致条数暴涨时 CI 立刻失败,把性能契约固化进测试,比上线后靠 APM 发现早得多。
