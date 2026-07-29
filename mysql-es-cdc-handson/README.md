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

The [Canal and Adapter evidence boundary](docs/01-canal-boundary.md) records black-box behavior for the official 1.1.8 Adapter. `products_adapter_v1` is a disposable comparison index; it is never the serving index and is not evidence of the final consistency contract. The pinned byte/1000 experiment observed target coercion to `-24`, not the intended Bulk partial failure.

The standard complete M1 command sequence is:

```bash
make scenario-m1
make gate-m1
```

`gate-m1` assumes `scenario-m1` has already generated the ignored runtime evidence and rendered boundary. It first verifies all four M1 scenarios and the documentation, then removes only the two Adapter comparison services and proves their containers are absent before resetting named project volumes and running the fresh M0 smoke gate. It does not rerun the dynamic M1 scenarios.

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

Compose 将 Elasticsearch 的 `cluster.routing.allocation.disk.threshold_enabled` 设为 `false`，只为避免开发机磁盘水位导致 single-node lab 的唯一 primary shard 永久不分配，从而保证实验可重复。该设置关闭了生产环境重要的磁盘保护，绝不是生产配置建议；生产环境必须保留磁盘水位保护并通过容量、告警和扩容处理磁盘压力。

`make bootstrap-products-v2` 的安全前提是 single-writer：执行期间不得有其他管理员并发修改同名 index template、physical index 或 aliases。脚本先只读检查完整兼容性，再执行创建，并用最终读取检测明显竞态；最终检查不能回滚已经发生的竞态，因此这里不声称面对任意并发管理操作仍可 fail closed。

## Canal 1.1.8 边界

本实验固定的 release-native ACK cursor 是 `/home/admin/canal-data/products/meta.dat`，不是 parser 的 `parse.dat`。正式 smoke 在 normal stop 前先证明 ACK、cursor persist 和 Kafka end offsets，再验证 exact resume。Canal 1.1.8 static-destination normal stop 可能记录已知 upstream `future=null` `NullPointerException`；evidence 只按本次 stop 观察 `present/absent`，它既不是成功条件，也不能推广成“无害”或 clean/safe shutdown。

完整目标与不变量见 [docs/00-goals-and-invariants.md](docs/00-goals-and-invariants.md)。

## M2–M3：自定义可靠消费链路

机制与边界见 [可靠消费链路](docs/02-reliable-pipeline.md) 和
[失败模型](docs/03-failure-model.md)。标准工作流使用 Java 21：

```bash
make bootstrap-index
make scenario-m3       # 九个 raw-first 场景；验收时从 reset 环境完整运行两轮
make gate-m2-m3        # 模块测试、matrix、health/metrics、DLQ=0、tracked clean
```

`/internal/dlq/**` 与 `/internal/record-dlq/**` 仅是绑定本机端口的实验/admin
接口，不是开放、无鉴权生产接口的建议。M3 证明 at-least-once、external
revision fencing 和已知失败可恢复；它不检测 binlog/Kafka gap 或独立 projection
drift，也不宣称 MySQL 与 Elasticsearch 已获得全局最终一致性证明。

## M4 control-plane baseline

`source_change_watermark` 是从 reconciliation control-plane 安装时开始计数的
change epoch，不是既有业务数据的历史 mutation 总数。fresh 环境从 0 开始；在已有
数据的环境首次安装也从 0 开始，但只用于判断安装后扫描期间是否又发生业务事务。
重复执行 `bash infra/mysql/apply-reconciliation-control.sh` 会保留非零 epoch，不会
把既有 facts 冒充已计数历史，也不会重置已经推进的 watermark。

Task 1 只建立事务 watermark、持久化 reconciliation metadata 与 verifier 的独立
模块/拓扑边界；尚未实现 expected-document projection、diff、repair 或一致性判定。

## M4：独立对账与受控修复

[独立对账契约](docs/04-reconciliation.md)定义 PASS 的精确证明边界、consumer 与
verifier 的实现独立性、三类受控修复方式及其限制。标准命令为：

```bash
make reconcile    # 发起一次独立扫描
make scenario-m4  # 运行七类隔离故障矩阵
make verify-m4    # consumer/verifier 测试与完整 M4 场景门禁
```

M4 的最终一致性声明只针对 MySQL 事实仍然存在、日志无确认缺口且 source watermark
稳定的范围；修复后必须重新得到 zero-difference PASS，并同时满足 lag=0、DLQ=0、
无 active gap，状态才是 HEALTHY。确认的日志缺口仍交给 M5 rebuild，不属于 M4。

## M5：可验证的全量重建

[全量重建与无缺口切换 runbook](docs/05-rebuild-runbook.md)说明 `O_start`、一致性
快照、shadow replay、三分区 barrier、独立 physical-index verification 和原子 alias
边界。标准入口：

```bash
make scenario-m5
make verify-m5
make formal-final-m5 # latest clean HEAD, two fresh-volume rounds
```

M5 包含并发扫描、alias 边界前后崩溃、真实 Kafka retention gap，以及保留
`meta.dat` 证据的 MySQL binlog cursor rebootstrap。它能从仍存在的 MySQL 当前事实
重建 Elasticsearch；不能恢复已从 MySQL 消失且从未保留的历史，也不把 Canal CDC
组件本身描述为端到端最终一致性方案。
