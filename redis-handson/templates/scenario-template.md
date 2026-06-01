# Scenario: <一句话描述>

## 我想验证的问题

<一句话。例:「同一个 hash,字段数从 128 涨到 129 时 OBJECT ENCODING 会不会从 listpack 变 hashtable?」>

## 预期(写实验前的假设)

> **请在跑 lab 之前填这一段**。基于章节 README 教过的规则(不要查),把下列空格填上,写完单独 commit 一次("prediction only"),再开始跑。
>
> - 我以为触发条件是 _____,转换后编码变成 _____。
> - 我以为内存/性能会 _____。

## 环境

- compose: `00-lab/docker-compose.yml`
- 起 lab:`make up`(cluster scenario 用 `make up-cluster && make cluster-init`)
- 造数据:`make load N=<N>`(如适用)

## 步骤

1. ...
2. ...

## 实机告诉我(跑完当天填)

```
<贴 redis-cli 输出 / INFO 片段 / SLOWLOG / LATENCY 报告>
```

观察到的关键事实:

- ...

## ⚠️ 预期 vs 实机落差

<这是核心输出。完全对应预期 = scenario 太简单或预期太模糊。>

- 我以为:……
- 实际:……
- 我学到:……

## 连到的面试卡

- `99-interview-cards/q-xxx.md`
