"""评估用的 golden set。

每条 = 一个 query + 它的答案落在哪个 section 的第几个 paragraph。
- para_idx 指向「最直接回答问题的那一段」→ 用于 Recall / MRR。
- 整个 section 的所有段 → 用于「完整度」(返回内容是否覆盖了答案所在的完整小节)。

注意：很多 query 的答案那一段，单独看是不够的（比如「被限流返回什么」
只给 429 那句，但读者还需要同节的 QPS 和令牌桶上下文）。这正是 small-to-big
想解决的：检索命中精确的小段，却把整节的上下文一起还给 LLM。
"""

GOLDEN = [
    {"query": "免费版每天能调用多少次 API？", "section_id": "billing.quota", "para_idx": 0},
    {"query": "配额什么时候重置？没用完会累积吗？", "section_id": "billing.quota", "para_idx": 1},
    {"query": "怎么提升每天的调用配额上限？", "section_id": "billing.quota", "para_idx": 2},
    {"query": "账单是什么时候出的？", "section_id": "billing.invoice", "para_idx": 0},
    {"query": "怎么开发票？多久能拿到？", "section_id": "billing.invoice", "para_idx": 1},
    {"query": "欠费不付会怎么样？", "section_id": "billing.invoice", "para_idx": 2},
    {"query": "API 的限流是多少？", "section_id": "ratelimit.limit", "para_idx": 0},
    {"query": "被限流了会返回什么？要等多久再试？", "section_id": "ratelimit.limit", "para_idx": 1},
    {"query": "遇到 429 之后应该怎么重试？", "section_id": "ratelimit.retry", "para_idx": 0},
    {"query": "重试的时候怎么避免重复扣费？", "section_id": "ratelimit.retry", "para_idx": 1},
    {"query": "一个项目能创建几个 API key？", "section_id": "auth.key", "para_idx": 0},
    {"query": "API 密钥泄露了应该怎么处理？", "section_id": "auth.key", "para_idx": 1},
    {"query": "access token 的有效期是多久？", "section_id": "auth.oauth", "para_idx": 0},
    {"query": "refresh token 能用多长时间？", "section_id": "auth.oauth", "para_idx": 1},
    {"query": "单个文件最大能上传多大？", "section_id": "storage.upload", "para_idx": 0},
    {"query": "大文件要怎么做分片上传？", "section_id": "storage.upload", "para_idx": 1},
    {"query": "上传的文件别人能直接访问到吗？", "section_id": "storage.upload", "para_idx": 2},
    {"query": "回收站里的文件能保留多久？", "section_id": "storage.retention", "para_idx": 0},
    {"query": "Webhook 回调地址有什么要求？", "section_id": "webhook.config", "para_idx": 0},
    {"query": "回调失败了会重试吗？能手动重放吗？", "section_id": "webhook.config", "para_idx": 1},
    {"query": "怎么校验回调请求确实来自平台？", "section_id": "webhook.config", "para_idx": 2},
    {"query": "支持哪些区域？数据会跨区域复制吗？", "section_id": "region.deploy", "para_idx": 0},
    {"query": "平台通过了哪些合规认证？", "section_id": "region.compliance", "para_idx": 0},
    {"query": "审计日志会保留多久？", "section_id": "region.compliance", "para_idx": 1},
]
