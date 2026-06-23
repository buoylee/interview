# binlog 的 ROW / STATEMENT / MIXED 怎么选？

## 一句话回答

**STATEMENT** 只记 SQL 原文（省空间，但含 `NOW()`/`UUID()` 等非确定性函数时主从结果不一致，RC 隔离级别下也不被允许）；**ROW** 记每个被改行的前后镜像（绝对确定、主从一致，但大批量 DML 时 binlog 暴涨）；**MIXED** 是「能 STATEMENT 就 STATEMENT、有风险才切 ROW」的折衷。生产默认 **ROW**（8.0 默认）。

## 要点

- 实测：一条 UPDATE 改 1 万行，**STATEMENT 339 字节，ROW 477940 字节，≈1409 倍**。
- ROW 的体积 = O(行数 × 行宽)，所以「看似无害」的批量 UPDATE/DELETE 会瞬间写几百 MB binlog。
- `binlog_row_image=minimal` 只记被改列 + 主键，能显著压小 ROW binlog。

## 证据链接

- 实测 ROW vs STATEMENT 体积 1409 倍：[ch07 Scenario 02](../07-logs-and-crashsafe/scenarios/02-binlog-row-vs-statement-size.md)
- 章节原理：[ch07 §3.5](../07-logs-and-crashsafe/README.md)

## 易追问的延伸

- **Q: ROW 下大批量 DML 怎么办？** → 分批（每批几千行 + sleep），别一条语句扫全表；否则撑爆磁盘 + 拖垮从库重放（主从延迟）。
- **Q: 为什么 ROW 更安全？** → 直接记结果行，主从不依赖「重新执行 SQL 算出相同结果」，避开所有非确定性。
