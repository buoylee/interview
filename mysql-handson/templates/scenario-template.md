# Scenario: <一句话描述>

## 我想验证的问题

<一句话。例：「同一条 SELECT，在 1k 行和 100w 行时优化器是否会走不同的计划？」>

## 预期（写实验前的假设）

<把你「以为」的行为写下来，越具体越好。写完才能跑，跑完才能对照。>

> 纪律：本节填完后请单独 commit 一次，再开始跑 lab。

## 环境

- compose: `00-lab/docker-compose.yml`
- 起 lab：`make up`
- schema：`init/01-create-schema.sql` 自动创建 `sbtest1`、`user_profile`
- 灌数据：`make load ROWS=<N>`（如适用）

## 步骤

1. ...
2. ...
3. ...

## 实机告诉我（跑完当天填）

```
<贴 explain / SHOW STATUS / SHOW ENGINE INNODB STATUS / 慢查日志片段>
```

观察到的关键事实：

- ...
- ...

## ⚠️ 预期 vs 实机落差

<这是本 scenario 的核心输出。完全对应预期 = scenario 太简单或预期太模糊。>

- 我以为：……
- 实际：……
- 我学到：……

## 连到的面试卡

- `99-interview-cards/q-xxx.md`
