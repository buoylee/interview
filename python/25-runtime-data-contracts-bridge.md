# 25 · 运行时数据契约（桥接章）

> **一句话定位**：类型注解描述意图，Pydantic 在不可信数据进入或可信数据离开服务时执行契约；领域规则仍属于领域层。本章只负责选型和导航，不重复 Pydantic API 教程。

## 一页定位图

```text
源码中的值 ── 静态类型（mypy/pyright）──▶ 运行前发现内部调用的类型矛盾
外部 payload ── 运行时验证（Pydantic）──▶ 已解析、满足结构约束的边界 DTO
边界 DTO ── 显式映射 ──▶ command / domain ── 领域规则 ──▶ 业务决定
domain / view ── 序列化（Pydantic）──▶ 白名单 JSON / event
                     └── JSON Schema ──▶ 文档、golden diff、兼容性审查
```

五件事不能混为一谈：静态类型不读取线上 JSON；运行时验证不证明业务决定正确；序列化是独立的出站边界；JSON Schema 描述结构但不自动证明兼容；领域规则不应被 transport model 接管。

## 怎么选数据载体

| 选择 | 适合 | 不适合 / 迁移信号 |
|------|------|-------------------|
| `dataclass` | 边界内已可信的数据、轻量值对象，需要生成 init/equality | 需要从 JSON 执行复杂验证、别名、schema 或安全序列化时转向 Pydantic |
| `TypedDict` | 给静态检查器描述 dict 形状，保留原生 mapping 互操作 | 它不做运行时验证；外部 payload 必须另加验证边界 |
| Pydantic model | HTTP/MQ/config 等不可信边界，需要解析、约束、错误、序列化或 JSON Schema | 纯领域行为、实体生命周期都塞进去时应拆层 |
| 普通领域类 | 业务行为、不变量、聚合生命周期，需要与框架解耦 | 直接接收原始 dict 或直接对外 dump 时缺少边界契约 |

经验法则：**边界用 Pydantic，边界内按行为选择 dataclass 或普通类，TypedDict 只提供静态形状。** 不要为了“全项目统一”强迫一个模型承担四种职责。

## 最小 inbound 示例

下面只展示边界形状；strict、validator、分层、错误和演进的完整做法进入 [`../python-pydantic/`](../python-pydantic/)：

```python
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


class CreateOrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: Annotated[StrictStr, Field(pattern=r"^SKU-[A-Z0-9-]+$")]
    quantity: Annotated[StrictInt, Field(gt=0, le=100)]


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: Annotated[StrictStr, Field(min_length=8)]
    items: Annotated[list[CreateOrderItem], Field(min_length=1)]


request = CreateOrderRequest.model_validate_json(raw_body)
command = to_create_order_command(request)
```

## 与其他章节的边界

- [`09-typing.md`](09-typing.md)：类型注解、`TypedDict`、`Annotated` 与静态检查；结论仍是“注解本身不执行运行时校验”。
- [`12-testing.md`](12-testing.md)：pytest、fixture、mock 的通用方法；数据契约的 golden、边界和兼容性矩阵在 Pydantic 深水教程。
- [`20-production-skeleton.md`](20-production-skeleton.md)：项目骨架、12-factor、日志和启动错误边界；settings 的来源优先级、缓存和多 worker 行为在 Pydantic 第 12 章。
- [`23-data-access-bridge.md`](23-data-access-bridge.md)：driver、ORM、事务和 repository 导航；Pydantic 不替代 SQLAlchemy model 或事务边界。
- [`../fastapi-ops/`](../fastapi-ops/)：FastAPI 部署、指标、追踪、日志、压测和调优；这里仅把 Web 框架当作调用契约的薄适配器。

## Java / Go 对照

| 关注点 | Java | Go | Python + Pydantic |
|--------|------|----|-------------------|
| 静态类型 | `javac` 强制，DTO 字段编译期检查 | `go build` 强制，struct 字段编译期检查 | 注解由 mypy/pyright 可选检查，解释器不强制 |
| 外部输入 | Jackson 绑定 + Bean Validation | `encoding/json` + validator/手写检查 | Pydantic 合并解析、约束和结构化错误 |
| 出站协议 | 独立 response DTO / Jackson view | 专用 response struct / tags | 专用 view model + serializer / include-exclude |
| schema | OpenAPI/注解与生成器 | struct/tag + 生成器 | CoreSchema 派生 JSON Schema，但兼容性仍需测试 |
| 领域模型 | entity/value object 不应等同 transport DTO | domain struct 可与 wire struct 分开 | 普通类/dataclass 可保持无 Pydantic 依赖 |

三种语言的架构结论相同：**wire shape、用例输入、领域对象和输出视图有不同变化原因**。Python 的额外风险是类型注解看起来像 Java/Go 类型，却不会自动拦住运行时输入。

## 桥接面试卡

**Q1：已经有类型注解，为什么还要 Pydantic？**  注解主要供人和静态工具读取，线上 JSON 在运行时才出现；Pydantic 在信任边界把未知输入转成满足结构约束的值，二者互补。

**Q2：所有业务对象都继承 `BaseModel` 是否更统一？**  不。边界模型关心协议、alias、错误和序列化，领域对象关心业务不变量与生命周期；统一基类会让外部协议变化渗入核心。

**Q3：JSON Schema snapshot 通过就能宣布兼容吗？**  不能。snapshot 只发现变化，还要按 producer/consumer 方向判断 required、约束和语义，并用旧样本与新模型交叉测试。

**Q4：Pydantic 能替代数据库约束或 API 鉴权吗？**  不能。它验证当前进程看到的结构和值；唯一性、并发一致性由数据库/事务保证，权限由应用服务与安全边界决定。
