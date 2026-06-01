# Scenario 02: KEYS vs SCAN —— 阻塞全库扫 vs 渐进迭代

## 我想验证的问题

`KEYS *` 在 10 万 key 上要扫多久、会不会进 SLOWLOG（即阻塞）？`SCAN` 走完同样的库需要几次迭代、单次返回多少、会不会进 SLOWLOG？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.4/§4 + 12 章，不要查）：
>
> - `KEYS *`（10 万 key）大约耗时 _____ 微秒，会不会进 SLOWLOG？_____
> - `SCAN`（COUNT 1000）走完 10 万 key 大约 _____ 次迭代；单次会不会阻塞、会不会进 SLOWLOG？_____
> - `SCAN` 的 COUNT 是「精确返回数量」还是「建议值」？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up` + `make load N=100000`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up && make load N=100000
R(){ docker compose exec -T redis redis-cli "$@"; }
# KEYS *:阈值降到 1ms,看是否进 slowlog
R config set slowlog-log-slower-than 1000 >/dev/null; R slowlog reset >/dev/null
R keys '*' >/dev/null
echo "KEYS* slowlog: $(R slowlog get 1 | sed -n '3,5p' | tr '\n' ' ')"
# SCAN:游标迭代,数迭代次数和单次最大返回
cur=0; iters=0; mx=0
while :; do
  out=$(R scan $cur count 1000); cur=$(echo "$out"|head -1|tr -d '\r')
  n=$(echo "$out"|tail -n +2|wc -l|tr -d ' '); [ $n -gt $mx ] && mx=$n
  iters=$((iters+1)); [ "$cur" = "0" ] && break; [ $iters -gt 500 ] && break
done
echo "SCAN: $iters 次迭代走完, 单次最多返回 $mx 个 key"
R slowlog reset >/dev/null
cur=0; while :; do out=$(R scan $cur count 1000); cur=$(echo "$out"|head -1|tr -d '\r'); [ "$cur" = "0" ] && break; done
echo "SCAN 是否进 slowlog(阈值1ms): len=$(R slowlog len)"
R config set slowlog-log-slower-than 10000 >/dev/null
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
KEYS* slowlog: 4712 微秒  "keys *"           ← 一条命令阻塞 4.7ms,进了 slowlog
SCAN: 100 次迭代走完, 单次最多返回 1004 个 key  ← COUNT 1000 是建议值,实际略有出入
SCAN 是否进 slowlog: len=0                     ← 每次迭代都很快,不阻塞,不进 slowlog
```

观察到的关键事实：

- `KEYS *` 是**一条 O(N) 命令**：扫完 10 万 key 用了 4.7ms，全程占住单线程，进了 SLOWLOG。
- `SCAN` 把同样的活拆成 **100 次小迭代**，每次只扫一小批（~1000），单次极快、不进 SLOWLOG，期间其他命令可以插队执行。
- `COUNT 1000` 是**建议值不是精确值**（单次最多返回 1004）；`SCAN` 还可能返回重复 key、不保证一次性看到 rehash 中的全部 key（弱一致遍历）。

## ⚠️ 预期 vs 实机落差

- 我以为：`KEYS *` 和 `SCAN` 都是遍历，慢一点而已，差别不大。
- 实际：差别是**「一次 O(N) 阻塞」vs「N 次 O(小) 不阻塞」**。`KEYS *` 那 4.7ms 里 Redis 谁也不理；`SCAN` 100 次迭代之间随时让出单线程。
- 我学到：(1) 线上**绝不用 `KEYS`**,一律 `SCAN`（同理 `HSCAN`/`SSCAN`/`ZSCAN`）。(2) `SCAN` 用游标:第一次 cursor=0,用返回的 cursor 续扫,到 0 结束;COUNT 只是 hint。(3) `SCAN` 是弱一致遍历（可能重复、rehash 期间可能漏/重），用于「尽量扫一遍」而非「精确快照」。

## 连到的面试卡

- `99-interview-cards/q-redis-single-thread.md`
