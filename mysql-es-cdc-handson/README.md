# MySQL → Canal → Elasticsearch 最终一致性实战

## 先给结论

Canal 是 MySQL binlog CDC（变更数据捕获）/增量订阅组件，不是端到端最终一致性方案。M0 只证明：MySQL 业务事实和 revision 在一个本地事务提交后，Canal 1.1.8 能把对应行变化发布到 Kafka。Kafka 中出现消息不等于 Elasticsearch 已经收敛。

## M0 能证明什么

- `product-service` 只提交 MySQL，不同步写 Kafka 或 Elasticsearch；
- Canal 1.1.8 读取 MySQL 8.4 的 `ROW`/`FULL` binlog；
- `product_id` 参与 Canal `partitionHash`，同一商品稳定进入同一 partition；
- Canal 生成的 Kafka record key 为 `null`，`product_id` 从 flat-message `data` 解析；
- `evidence/m0/canal-position.json` 证明 revision 1 的 ACK 派生 cursor 已持久化到 `/home/admin/canal-data/products/meta.dat`，Canal-only normal restart 保持 cursor/offset 身份不变，revision 2 只出现在预期 next offset 一次；
- `evidence/m0/version-manifest.json` 记录 pinned registry dependency 的本地 image ID 与真实 RepoDigest，以及本地构建应用镜像的 image ID。

M0 尚未提供 Elasticsearch consumer/write、逐 Bulk item 判定、revision 防倒退、DLQ、独立对账或全量重建，因此不宣称最终一致性、exactly-once processing 或 shutdown safety。

## M1: official Adapter comparison

The [Canal and Adapter evidence boundary](docs/01-canal-boundary.md) records black-box behavior for the official 1.1.8 Adapter. `products_adapter_v1` is a disposable comparison index; it is never the serving index and is not evidence of the final consistency contract. The pinned byte/1000 experiment observed target coercion to `-24`, not the intended Bulk partial failure; run `make scenario-m1` and `make verify-m1` to regenerate and verify the ignored runtime evidence and rendered boundary.

## 运行

前置：Docker Compose v2、Java 21、`jq`、`curl`。Maven Wrapper 已固定构建工具；只有重新生成 Wrapper 时才需要本机 Maven。请将 `JAVA_HOME` 指向本机的 Temurin 21；项目不硬编码机器路径。

```bash
make reset
make verify
make smoke-m0
make evidence
```

验收 fresh-run 可重复性时，完整执行两次：

```bash
make reset && make smoke-m0
make reset && make smoke-m0
```

本地端口：product-service 8081、MySQL 3308、Kafka 29092、Canal 11111/11112、Elasticsearch 9200、Toxiproxy API 8474。consumer/verifier 仅在 `m0-tools` profile 下定义，预留 8082/8083，默认不启动。仓库中的账号密码只用于本地实验，不得用于共享或生产环境。

## Canal 1.1.8 边界

本实验固定的 release-native ACK cursor 是 `/home/admin/canal-data/products/meta.dat`，不是 parser 的 `parse.dat`。正式 smoke 在 normal stop 前先证明 ACK、cursor persist 和 Kafka end offsets，再验证 exact resume。Canal 1.1.8 static-destination normal stop 可能记录已知 upstream `future=null` `NullPointerException`；evidence 只按本次 stop 观察 `present/absent`，它既不是成功条件，也不能推广成“无害”或 clean/safe shutdown。

完整目标与不变量见 [docs/00-goals-and-invariants.md](docs/00-goals-and-invariants.md)。
