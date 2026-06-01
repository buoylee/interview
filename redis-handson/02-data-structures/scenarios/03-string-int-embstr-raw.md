# Scenario 03: String int / embstr / raw 三态与 44 字节边界

## 我想验证的问题

String 在什么情况下是 `int` / `embstr` / `raw`？embstr 与 raw 的分界精确在哪个长度？对一个 embstr 做 `APPEND` 会发生什么？一个超过 int64 范围的纯数字串还是 `int` 吗？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1/§3.2/§6，不要查）：
>
> - 纯整数值 → 编码 _____。
> - 短字符串（≤ _____ 字节）→ `embstr`，超过 → `raw`。
> - 对 embstr `APPEND` 一个字符后 → 编码变 _____（因为 _____）。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R` = `docker compose exec -T redis redis-cli`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R set s1 12345;                              R object encoding s1   # int?
R set s2 hello;                              R object encoding s2   # embstr?
R set s3 "$(printf 'x%.0s' $(seq 1 44))";    R object encoding s3   # 44B: embstr?
R set s4 "$(printf 'x%.0s' $(seq 1 45))";    R object encoding s4   # 45B: raw?
R set s5 ab; R append s5 c;                  R object encoding s5   # append 后: raw?
R set s6 99999999999999999999;               R object encoding s6   # 20 位超 int64: ?
```

## 实机告诉我（2026-06-01，Redis 7.4.9 实跑）

```
s1 "12345"                 -> int
s2 "hello"                 -> embstr
s3 44 个 x  (strlen=44)    -> embstr
s4 45 个 x  (strlen=45)    -> raw
s5 "abc"    (strlen=3)     -> raw      ← APPEND 之后,虽然只有 3 字节
s6 "99999999999999999999"  -> embstr   ← 超 int64,当普通字符串
```

观察到的关键事实：

- **44 字节是精确边界**：strlen=44 仍 embstr，45 就是 raw。
- **APPEND/SETRANGE 一旦动过，强制变 raw**，哪怕结果很短（s5 只有 3 字节也是 raw）——因为这类原地修改命令需要可追加扩容的 SDS，embstr 是只读式的一次性分配。
- **`int` 编码只给「能用 long 表示的整数」**：20 位数字超出 int64 范围，存成 embstr 而非 int。

## ⚠️ 预期 vs 实机落差

- 我以为：数字就是 int；短字符串 embstr、长的 raw，分界大概 40 几字节。
- 实际：分界**精确在 44**（≤44 embstr，>44 raw）；数字超 int64 就降级成 embstr；**APPEND 之后必为 raw**，与最终长度无关。
- 我学到：(1) 「44 字节」要记牢——这是 redisObject(16B)+SDS 头+终止符 凑满 64B jemalloc 块的结果。(2) 频繁 `APPEND` 的 key（如拼接日志）一定是 raw，享受 SDS 预分配；而一次性 `SET` 的短串是 embstr，省一次 malloc。(3) 把雪花 ID / 大数当 key 的 value 存时，别指望 `int` 省内存——超 int64 就是普通字符串了。