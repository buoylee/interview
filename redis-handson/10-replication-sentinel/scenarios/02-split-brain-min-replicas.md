# Scenario 02: 脑裂防护 —— min-replicas-to-write 拒写

## 我想验证的问题

`min-replicas-to-write 1` + `min-replicas-max-lag 2` 下，主在失去所有从（网络分区）且超过 max-lag 后，还能不能写？这怎么防脑裂丢数据？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.4，不要查）：
>
> - 有健康从时主写 → _____。
> - 网络断开所有从、超过 `min-replicas-max-lag` 后主写 → 返回 _____。
> - 这为什么能防脑裂导致的数据丢失？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up-sentinel`。用 `docker network disconnect` 真断开从（不是 pause，见 07 章 sc03 的教训）。

## 步骤

```bash
cd 00-lab && make up-sentinel
M(){ docker compose exec -T redis-m redis-cli "$@"; }
NET=$(docker compose ps redis --format '{{.Networks}}'|head -1)
R1=$(docker compose ps redis-r1 --format '{{.Name}}'); R2=$(docker compose ps redis-r2 --format '{{.Name}}')
until [ "$(M info replication 2>/dev/null|grep -c state=online)" = "2" ]; do sleep 1; done
M config set min-replicas-to-write 1
M config set min-replicas-max-lag 2
echo "正常(有从)写: $(M set k v1)"
docker network disconnect $NET $R1; docker network disconnect $NET $R2
sleep 5    # 等超过 max-lag(2s),主判定无健康从
echo "失去所有从且超 max-lag 后写: $(M set k v2)"
docker network connect $NET $R1; docker network connect $NET $R2
M config set min-replicas-to-write 0
make down-sentinel; docker compose up -d redis
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
正常(有从)写: OK
失去所有从且超 max-lag 后写: NOREPLICAS Not enough good replicas to write.
```

观察到的关键事实：

- 有健康从时主正常写 `OK`。
- 网络断开所有从、且超过 `min-replicas-max-lag`（2s）后，主对写命令返回 **`NOREPLICAS Not enough good replicas to write`**——主动**拒绝写入**。
- （注意:要等超过 max-lag 主才判定从"不健康";断开后立刻写还会成功，因为主还没察觉从已滞后。）

## ⚠️ 预期 vs 实机落差

- 我以为：主只要活着就一直能写,从挂了不影响主。
- 实际:配了 `min-replicas-to-write` 后,主在「健康从数不够」时**主动拒写**。这是用「**可用性**」换「**一致性**」:防的是脑裂——网络分区时,被孤立的旧主如果继续接受写,等哨兵在另一侧选了新主、旧主被降级,旧主这段写就全丢了;拒写就不会产生这些注定要丢的写。
- 我学到:(1) `min-replicas-to-write N` + `min-replicas-max-lag S`:少于 N 个从在 S 秒内 ack 就拒写。(2) 这是 CAP 里向 C 倾斜的取舍(分区时牺牲 A)。(3) max-lag 决定「多久算从掉了」——断开后不是立刻拒写,要等这个窗口(实测断开立刻写还 OK,等 5s 后才 NOREPLICAS)。

## 连到的面试卡

- `99-interview-cards/q-redis-replication-sentinel.md`
