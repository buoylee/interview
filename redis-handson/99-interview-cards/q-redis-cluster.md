# Redis Cluster:分片、路由、multi-key、故障转移？

## 一句话回答

Cluster 把 key 空间分成 **16384 槽**(`CRC16(key)%16384`)分给多 master 横向扩展;客户端靠 **MOVED**(永久换家、更路由表)/ **ASK**(迁移中临时)重定向;multi-key 必须**同槽**,用 **hash tag `{}`** 绑定;高可用靠 gossip 检测 + 过半 master 投票把从升主。

## 关键点

- **定位**:`CRC16(key) % 16384` → 槽 → 负责该槽的 master(sc01:foo→12182)。
- **MOVED vs ASK**:MOVED=槽永久归别人,客户端更路由表重连(sc01:`MOVED 12182 <ip>`);ASK=槽迁移中,这一次去目标节点(先 `ASKING`)、不更表。
- **multi-key 限制**:跨槽 multi-key 报 **CROSSSLOT**(sc02);hash tag `{u}` 只对 `{}` 内算槽 → 绑同槽。
- **故障转移**:gossip ping/pong 检测 → `cluster-node-timeout` 内不通标 **pfail** → 过半持槽 master 同意标 **fail** → 下线 master 的从被**过半 master 投票**选为新主接管槽。

## 实测证据

- 槽 + MOVED:KEYSLOT foo=12182;非 -c `SET foo`→`MOVED`;`-c` 自动重定向 OK。[sc01](../11-cluster/scenarios/01-slot-moved-redirect.md)
- hash tag:`MSET a b c`→CROSSSLOT;`{u}:a`/`{u}:b` 同槽 11826,MSET OK。[sc02](../11-cluster/scenarios/02-hash-tag-crossslot.md)

## 易追问的延伸

- **为什么 16384 而非 65536?** 槽位图每节点要维护并随心跳传播,16384 bit=2KB 够小;且 65536 在心跳包里太大。
- **cluster 支持事务/Lua 吗?** 仅限同槽 key(hash tag 绑定后可)。
- **扩容怎么做?** 新节点 meet 入群 → reshard 迁槽(迁移期 ASK 重定向),在线进行。
- **cluster vs 哨兵?** 哨兵=单份数据高可用(不分片);cluster=分片(扩容)+ 自带高可用。数据量小只要 HA 用哨兵,要扩容用 cluster。

## 证据链接

- 章节原理:[11-cluster](../11-cluster/README.md)
- 实测:[sc01 槽/MOVED](../11-cluster/scenarios/01-slot-moved-redirect.md)、[sc02 hash tag](../11-cluster/scenarios/02-hash-tag-crossslot.md)
- 故障转移自动切换实证(哨兵):[07 章 sc03](../07-distributed-locks/scenarios/03-failover-lock-loss.md)
