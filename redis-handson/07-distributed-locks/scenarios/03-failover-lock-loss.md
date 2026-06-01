# Scenario 03: 主从切换丢锁（pause 没丢 vs 真断网丢失 + 双重持有）

## 我想验证的问题

Redis 主从复制是异步的。如果客户端在 master 上加锁成功，master 在「把锁复制给 slave 之前」就宕机，sentinel 把 slave 升为新主——新主上还有这把锁吗？如果没有，是不是会出现「两个客户端同时持有同一把锁」？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.4，不要查）：
>
> - 实验 A：`pause`（冻结进程）两个 replica → master 加锁 → 杀 master → unpause → 故障转移。新主上锁还在吗？_____
> - 实验 B：`network disconnect`（真断网）两个 replica → 同样流程。新主上锁还在吗？_____
> - 锁若丢了，另一客户端能否再次 `SET NX` 成功（双重持有）？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up-sentinel`（1 主 2 从 + 3 哨兵）。容器名是 compose 自动名，用 `docker compose <svc>`。
- 关键技巧:检测故障转移完成要轮询 `sentinel get-master-addr-by-name` 直到地址**变化**（旧主未被判定下线时它返回旧地址，不能只判非空）。

## 步骤

```bash
cd 00-lab
NET=$(docker compose ps redis --format '{{.Networks}}' | head -1)
make up-sentinel
M(){ docker compose exec -T redis-m redis-cli "$@"; }
SN(){ docker compose exec -T redis-sn-1 redis-cli -p 26379 "$@"; }
until [ "$(M info replication 2>/dev/null | grep -c 'state=online')" = "2" ]; do sleep 1; done
ORIG=$(SN sentinel get-master-addr-by-name mymaster | head -1 | tr -d '\r')
R1=$(docker compose ps redis-r1 --format '{{.Name}}'); R2=$(docker compose ps redis-r2 --format '{{.Name}}')

# ===== 实验 A:pause 冻结进程 =====
docker compose pause redis-r1 redis-r2
M set lock:critical tokenA px 60000; echo "A) master 有锁=$(M get lock:critical)"
docker compose stop redis-m
docker compose unpause redis-r1 redis-r2
NEWIP="$ORIG"; i=0; until [ "$NEWIP" != "$ORIG" ] || [ $i -ge 45 ]; do NEWIP=$(SN sentinel get-master-addr-by-name mymaster 2>/dev/null|head -1|tr -d '\r'); i=$((i+1)); sleep 1; done
Q(){ docker compose exec -T redis-sn-1 redis-cli -h "$NEWIP" -t 2 "$@" 2>/dev/null|tr -d '\r'; }
echo "A) 新主 lock:critical=[$(Q get lock:critical)]"

# 重置后做实验 B(整段 down 再 up-sentinel,ORIG/R1/R2 重新取)…
# ===== 实验 B:network disconnect 真断网 =====
docker network disconnect $NET $R1; docker network disconnect $NET $R2
M set lock:critical tokenA px 60000; echo "B) master 有锁=$(M get lock:critical)"
docker compose stop redis-m
docker network connect $NET $R1; docker network connect $NET $R2
NEWIP="$ORIG"; i=0; until [ "$NEWIP" != "$ORIG" ] || [ $i -ge 45 ]; do NEWIP=$(SN sentinel get-master-addr-by-name mymaster 2>/dev/null|head -1|tr -d '\r'); i=$((i+1)); sleep 1; done
echo "B) 新主 lock:critical=[$(Q get lock:critical)]"
echo "B) 另一客户端重抢=[$(Q set lock:critical tokenB nx px 60000)]"

make down-sentinel; docker compose up -d redis    # 收尾,回到单机
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
实验 A(pause): 新主 lock:critical=[tokenA]        ← 锁"幸存"了!
实验 B(真断网): 新主 lock:critical=[]              ← 锁丢了
              另一客户端重抢=[OK]                   ← 双重持有!
故障转移耗时 ~18–29s(down-after 5s + 选举)
```

观察到的关键事实：

- **实验 A 锁没丢**：`pause` 只冻结 replica 的**进程**，master 早已把 `SET lock:critical` 发进了 replica 的**内核 TCP 接收缓冲**；`unpause` 后 replica 从缓冲补读并应用，所以被提升的新主**有**这把锁。
- **实验 B 锁丢了 + 双重持有**：`network disconnect` 在网络层真正切断，复制字节根本没送到 replica；新主升上来没有 `lock:critical`，第二个客户端 `SET NX` 返回 OK——**两个客户端同时"持有"同一把锁**。

## ⚠️ 预期 vs 实机落差

- 我以为：主从切换肯定丢锁，pause 掉 replica 再杀主就能复现。
- 实际：**pause 复现不出来**——TCP 缓冲让复制字节在 unpause 后补达，锁幸存;**只有真网络分区（写入的字节根本没发出去）才丢锁**。这个差别本身就说明：异步复制的丢锁窗口是「master 确认写入 → 字节尚未离开 master → master 此刻猝死」这一**窄但真实**的瞬间。
- 我学到：(1) 单实例（含主从）Redis 锁有**真实的丢锁窗口**，虽窄但在故障时会爆发成「双重持有」。(2) 这正是 **RedLock**（N 个独立 master 过半）和更根本的 **fencing token**（被保护资源校验单调递增 token，拒绝旧持有者）存在的理由——锁是性能优化，fencing 才是正确性保证。(3) 做实验要分清「进程冻结」与「网络分区」：模拟分布式故障必须在**网络层**断，否则内核缓冲会骗过你。

## 连到的面试卡

- `99-interview-cards/q-redlock-controversy.md`
