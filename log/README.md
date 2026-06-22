# 后端服务日志规范

> 适用于：Python FastAPI 技术栈，5 人小团队，VM + Docker 混合部署
>
> 📌 **本目录是 Python/FastAPI 专属的落地深切**。若想看「怎么把日志写好」这个动作的**跨语言(Python/Go/Java)教学版**——等级 rubric、log-or-throw、配置坑、三语言可跑范例——见 [`../logging/`](../logging/README.md)。两者关系:`logging/` 教写法、`observability/` 教收集查询、本目录是 Python 深切范例。

## 文档目录

| 文档 | 内容 |
|------|------|
| [01-日志格式规范](./01-日志格式规范.md) | 日志级别、JSON 字段定义、敏感信息脱敏 |
| [02-FastAPI 日志配置](./02-FastAPI日志配置.md) | structlog 配置、请求中间件、业务日志使用示例 |
| [03-部署与日志采集](./03-部署与日志采集.md) | VM / Docker 双环境配置、Loki + Grafana 搭建 |
| [04-落地检查清单](./04-落地检查清单.md) | 逐项检查，确保规范落地 |
| [05-无日志系统时的 FastAPI 日志配置](./05-无日志系统时的FastAPI日志配置.md) | 没有 ELK/Loki，日志写本地文件的完整方案 |
