"""小型知识库语料（虚构的 CloudAPI 平台文档）。

结构是两层：doc → section → paragraphs。
- 一个 paragraph = 一个「小块」(small chunk)，embedding 准、但上下文不全。
- 一个 section   = 一个「大块」(big chunk)，上下文全、但噪声多。
small-to-big 的全部意义就是：用小块检索，命中后把它所在的 section 还回去。

故意让每个 section 有多个 paragraph 且话题相关，这样：
- 单个小块永远无法覆盖整节 → 「完整度」指标能区分 small vs big。
- 同节的兄弟块语义相近 → 检索候选里常一起出现 → 触发 auto-merge 上卷。
"""

DOCS = [
    {
        "doc_id": "billing",
        "title": "计费与配额",
        "sections": [
            {
                "section_id": "billing.quota",
                "heading": "调用配额",
                "paras": [
                    "免费版每个项目每天可调用 1000 次 API，超出后所有请求返回 429 状态码。",
                    "配额在每天 UTC 00:00 重置，未用完的额度不会累积到次日。",
                    "企业版可在控制台申请把每日配额提升到最高 100 万次。",
                ],
            },
            {
                "section_id": "billing.invoice",
                "heading": "账单与发票",
                "paras": [
                    "账单按自然月出具，每月 1 号生成上一个月的用量明细。",
                    "发票需在控制台「财务」页提交开票信息，提交后 5 个工作日内寄出。",
                    "逾期未付费的账户会在 7 天宽限期后被暂停写入权限。",
                ],
            },
        ],
    },
    {
        "doc_id": "ratelimit",
        "title": "限流与重试",
        "sections": [
            {
                "section_id": "ratelimit.limit",
                "heading": "限流规则",
                "paras": [
                    "默认限流为每个 API key 每秒 100 次请求（100 QPS）。",
                    "触发限流时返回 429，响应头 Retry-After 会给出建议的等待秒数。",
                    "突发流量可使用令牌桶预留，最高允许 2 倍瞬时峰值。",
                ],
            },
            {
                "section_id": "ratelimit.retry",
                "heading": "重试建议",
                "paras": [
                    "客户端应对 429 和 5xx 采用指数退避重试，初始等待 1 秒、最多重试 5 次。",
                    "重试请求必须带上幂等键 Idempotency-Key，避免重复扣费。",
                ],
            },
        ],
    },
    {
        "doc_id": "auth",
        "title": "认证与密钥",
        "sections": [
            {
                "section_id": "auth.key",
                "heading": "API 密钥",
                "paras": [
                    "每个项目最多可创建 10 个 API key，密钥仅在创建时完整显示一次。",
                    "密钥泄露时应立即在控制台吊销，吊销后 60 秒内全网生效。",
                    "建议为测试和生产环境使用不同密钥并打上标签区分。",
                ],
            },
            {
                "section_id": "auth.oauth",
                "heading": "OAuth 授权",
                "paras": [
                    "第三方应用通过 OAuth 2.0 授权码模式接入，access token 有效期为 2 小时。",
                    "refresh token 有效期 30 天，可用于静默刷新 access token。",
                ],
            },
        ],
    },
    {
        "doc_id": "storage",
        "title": "存储与文件",
        "sections": [
            {
                "section_id": "storage.upload",
                "heading": "文件上传",
                "paras": [
                    "单个文件最大 5 GB，超过该大小必须使用分片上传接口。",
                    "分片上传每片建议 8 MB，所有分片上传完成后调用 complete 接口合并。",
                    "上传的文件默认私有，需显式生成带签名的临时 URL 才能被公开访问。",
                ],
            },
            {
                "section_id": "storage.retention",
                "heading": "保留策略",
                "paras": [
                    "回收站中的文件保留 30 天，超过后永久删除且不可恢复。",
                    "开启合规模式后，文件在保留期内不可被删除（WORM 模式）。",
                ],
            },
        ],
    },
    {
        "doc_id": "webhook",
        "title": "事件与回调",
        "sections": [
            {
                "section_id": "webhook.config",
                "heading": "回调配置",
                "paras": [
                    "Webhook 回调地址必须是 HTTPS，且要通过一次握手验证才能激活。",
                    "每个事件最多重试 24 小时，采用递增间隔；失败事件可在控制台手动重放。",
                    "回调请求带 X-Signature 头，使用项目密钥做 HMAC-SHA256 签名校验。",
                ],
            },
        ],
    },
    {
        "doc_id": "region",
        "title": "区域与合规",
        "sections": [
            {
                "section_id": "region.deploy",
                "heading": "区域部署",
                "paras": [
                    "目前支持 cn-north、ap-southeast、us-east 三个区域，数据不跨区域复制。",
                    "区域一经创建不可更改，迁移需要新建项目并重新导入数据。",
                ],
            },
            {
                "section_id": "region.compliance",
                "heading": "合规认证",
                "paras": [
                    "平台已通过 SOC2 Type II 和 ISO 27001 认证。",
                    "审计日志默认保留 365 天，企业版可延长至 3 年。",
                ],
            },
        ],
    },
]
