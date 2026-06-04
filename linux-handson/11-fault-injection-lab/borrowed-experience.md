# 借来的经验:公开复盘阅读轨

> 🎯 你没大厂经验,但别人的惨案是公开的。**读公开复盘 = 白嫖别的工程师最惨的那天**,瞬间扩大你的「故障模式库」——这是补「大厂经验」里最高杠杆的一招。
> 读法:别当故事看。每篇问自己三件事——**①触发器是什么?②怎么放大的?③本该怎么防?**(对照 [场景 10 的三要素](./scenarios/10-cascading-failure.md))。

---

## 一、必读源

- **`danluu/post-mortems`**(GitHub)—— 最全的公开复盘合集,先收藏。
- **k8s.af**(k8s failure stories)—— 容器/k8s 翻车故事集。
- **GitLab 公开复盘** + **Cloudflare / AWS / GCP / Azure** 的官方事故博客 —— 一手、详尽。
- 读物:Richard Cook《How Complex Systems Fail》(18 条,极短)、Google SRE Book 的 Postmortem 章节。
- 论文:《Metastable Failures in Distributed Systems》(HotOS 2021)。

## 二、经典案例 → 映射到本道场的场景

| 事故 | 一句话教训 | 对应场景 |
|------|-----------|---------|
| **Cloudflare 2019-07-02**:一条 WAF 正则灾难性回溯,把所有 CPU 打满,全球宕机 | 一个烂正则能拖垮全网;CPU 高要能定位到那段代码 | [01 CPU 饱和](./scenarios/01-cpu-saturation.md) |
| **GitLab 2017-01-31**:误删生产数据库目录,且多种备份都失效 | 「先留证据再操作」「备份要验证能恢复」;复盘要 blameless | [复盘模板](./postmortem-template.md) + [07 心法](../07-troubleshooting-playbook/) |
| **AWS S3 us-east-1 2017-02-28**:运维一条命令打错,误下线过多服务器,拖垮 S3 | **爆炸半径**:危险操作要限制影响范围、要能减载 | [10 级联失败](./scenarios/10-cascading-failure.md) |
| **Knight Capital 2012**:部署不一致,旧代码路径被激活,45 分钟亏 4.4 亿美元 | 部署纪律;「一次只动一个变量」;灰度/回滚 | [07 心法](../07-troubleshooting-playbook/) |
| 各类 **retry storm / overload** 雪崩(danluu 合集里多见) | 慢依赖 + 无退避重试 + 容量无余量 = 亚稳态雪崩 | [07 重试风暴](./scenarios/07-retry-storm.md) · [10](./scenarios/10-cascading-failure.md) |

## 三、怎么把「读」变成「经验」

1. 每读一篇,用[复盘模板](./postmortem-template.md)的「根因分析(5 Whys)」结构**自己重写一遍**因果链。
2. 把它的故障形状**对号入座**到上面的场景;能在道场里复现的,就去复现一遍。
3. 攒一个自己的「故障模式 → 排查路径」小抄(接 [`99 面试卡`](../99-interview-cards/)),面试直接能讲。

> 面试里说「我读过 Cloudflare 那次正则 outage,自己在实验室用灾难性回溯复现过 CPU 打满,并用 `top -H` + jstack 定位到了那段代码」——这比一句含糊的「我在大厂处理过线上问题」有说服力得多。

➡️ 回到 [道场总纲](./README.md)。
