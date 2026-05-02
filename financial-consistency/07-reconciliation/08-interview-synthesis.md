# 08 面试与架构评审表达

## 一句话回答

对账不是事后补丁，而是金融一致性的事实闭环：它读取业务、账本、外部、清结算和人工事实，发现 Difference，创建 Case，通过 Repair、Review 和 Close 把差异收敛成可解释、可审计、可复核的结果。

## 标准回答结构

1. 先说明为什么需要对账：外部系统不可控，消息会重复乱序，账单会迟到，人工修复也会出错。
2. 再说明事实源：领域事实、账本事实、渠道事实、供应商事实、清结算事实和人工事实。
3. 再说明差错模型：Difference、Case、Repair、Review、Close。
4. 再说明对账类型：准实时、日终、T+N、专项重跑、人工复核。
5. 再说明修复边界：不能直接改平数据，必须追加事实和审批复核。
6. 最后说明验证：对账系统本身也要验证幂等、重跑安全、审计完整和关闭条件。

## 高频问题

### 为什么有了分布式事务还需要对账？

分布式事务和一致性模式只能降低部分执行窗口的风险，不能控制外部渠道、供应商账单、清算文件、迟到回调、人工修复和报表差异。真实金融系统必须用对账发现剩余差异，并把差异收敛成可审计事实。

### 渠道回调成功但本地失败怎么办？

不能直接把本地改成功，也不能重新扣款。应该用渠道 request id 和 channel transaction id 关联本地请求，创建 Difference 和 Case，补记可审计领域事实或账本事实，必要时进入 maker-checker。

### 本地成功但渠道账单没有怎么办？

先查询和等待账单窗口。如果 T+N 后仍无外部事实，要按履约状态拆分：不可逆履约前取消或 void 本地成功，并追加 reversal / compensating facts；不可逆履约后或确认外部少扣时，保留履约事实，转应收、供应商或渠道 claim、manual collection，或发起 fresh user-authorized payment flow。不能自动重扣或重试外部扣款；不能退款，除非有 external successful capture / settlement evidence，或确有应付负债。高风险和人工修复必须保留证据、maker-checker、Review 和 Close reason。

### 对账能不能直接把状态改成成功？

不能。对账只能生成 Difference、Case、Repair Command、Repair Fact、Review 和 Close。直接 update 状态会破坏审计链，也会让历史回放无法解释。

### 日终对账和准实时对账有什么区别？

准实时对账尽早暴露分叉，必须容忍短暂延迟。日终对账用账单、账本和清算批次做完整性检查，必须同时看明细和汇总。

### 人工修复如何避免变成不可审计后门？

人工修复必须有证据快照、maker-checker、幂等 Repair Command、Repair Fact、复核结果和关闭原因。人工备注不能替代审批和复核。

### 如何验证对账系统本身？

用异常 History 检查 Difference 幂等、Repair 幂等、重跑安全、Close 可解释、审计完整和报表只读。对账系统不能因为重跑、并发或人工操作制造新的不可解释事实。

## 评审底线

- 不接受“用了 Outbox/Saga/Temporal，所以不用对账”。
- 不接受“对账 SQL 直接 update 状态”。
- 不接受“只看汇总金额平，不看明细事实”。
- 不接受“workflow history、broker offset、日志或报表替代业务事实”。
- 不接受“unknown 直接判失败并重新外部扣款或退款”。
- 不接受“人工修复没有 maker-checker、证据和复核”。
- 不接受“Case 关闭没有关闭原因”。

## 面试收束

高级回答应该把对账讲成事实闭环：跨系统差异一定会发生，关键是系统能不能发现 Difference、创建 Case、执行幂等 Repair、完成 Review，并用 Close 证明差异已经被解释或进入可审计挂起。
