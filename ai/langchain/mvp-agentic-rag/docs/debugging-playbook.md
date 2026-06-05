# 排查 Playbook — Agentic RAG MVP

> 把「症状→组件→证据→修复→回归」流程在**本系统**上落地成可执行步骤。理论方法论见 [`../../../ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md`](../../../ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md)。

---

## 总览:通用排查路径

任何症状都从以下路径入手,逐步缩小范围:

```
1. 拿 X-Request-ID
      ↓
2. 打开 Langfuse → 搜 request_id → 展开 trace
      ↓
3. 逐 span 看(supervisor → retrieve → grade → generate → grounding_check)
      ↓
4. 对照 /metrics 看聚合指标(延迟 / token / 工具报错)
      ↓
5. 用 make eval 或 pytest 验证假设
      ↓
6. 修复 → make eval 回归 → 必要时补 golden case
```

---

## 获取 X-Request-ID

- **方式 1**:客户端在请求头带 `X-Request-ID: <uuid>`,API 层中间件原样透传并写回响应头。
- **方式 2**:若客户端未传,中间件自动生成 UUID4,写入响应头 `X-Request-ID`。
- **定位**:前端/调用方**必须存储**响应头的 `X-Request-ID`,否则事后无法关联 trace。
- **curl 示例**:
  ```bash
  curl -s -D - -X POST http://localhost:8000/chat \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"message": "...", "thread_id": "t-1"}' | grep -i x-request-id
  ```

---

## 在 Langfuse 中定位 trace

1. 打开 Langfuse UI(默认 `http://localhost:3000`)。
2. 导航到 **Traces** → 搜索框输入 `request_id:abc123`(或按时间窗口过滤)。
3. 点开 trace,展开 span 树:
   - `supervisor`:看 input(messages)→ output(RouteDecision)。路由到哪里?为什么?
   - `retrieve`:看 query → 返回的 chunk list(doc_id / score / content 前 100 字)。
   - `grade`:看 relevant=True/False,为什么?grader 的 reasoning 是什么?
   - `rewrite`(如有):看 rewritten query 是什么,和原 query 差别在哪。
   - `generate`:看 LLM prompt(含 chunks)→ answer。token 消耗多少?
   - `grounding_check`:看 grounded=True/False。
4. 记录每个 span 的关键值,用于下面的症状具体分析。

---

## 对照 /metrics

```bash
curl http://localhost:8000/metrics | grep rag_
```

关键指标:
- `rag_llm_tokens_total` — 累计 token 消耗,突增说明 context 膨胀。
- `rag_llm_calls_total` — LLM 调用次数,与请求数比值高说明反复 rewrite。
- `rag_tool_errors_total` — 工具调用报错次数,偶发/持续报错区分网络抖动和配置问题。
- `rag_llm_latency_seconds` — 看 `_bucket` 分位数,P95/P99 高说明单次 LLM 慢。

---

## 症状 1: 检索没命中 — 答案回答"未找到依据"但知识库里有相关文档

### 症状表现
- answer 是 `HEDGE_ANSWER`("未找到足够依据,无法可靠回答(依据不足)")。
- 用户明确知道知识库里有对应内容。

### 排查步骤

**Step 1: 看 Langfuse trace 的 retrieve span**

```
trace → retrieve span → output → chunks list
```
- chunks 是空的?还是有 chunk 但 grade 判不相关?

**Step 2a: 如果 chunks 是空的(检索失败)**

检查 dense 和 sparse 各自的命中情况:

```bash
# 直接查 pgvector dense 检索(在 Postgres)
psql $DATABASE_URL -c "
  SELECT doc_id, chunk_idx,
         embedding <=> (SELECT embedding FROM chunks WHERE doc_id='test' LIMIT 1) AS dist
  FROM chunks
  ORDER BY dist LIMIT 5;
"

# 检查 tsvector 稀疏检索
psql $DATABASE_URL -c "
  SELECT doc_id, chunk_idx, ts_rank(content_tsv, to_tsquery('simple', '关键词')) AS rank
  FROM chunks
  WHERE content_tsv @@ to_tsquery('simple', '关键词')
  ORDER BY rank DESC LIMIT 5;
"
```

可能原因:
- 文档未 ingest:检查 `SELECT COUNT(*) FROM chunks;` 是否为 0。
- 中文分词问题:sparse 路用 `simple` 分词器,中文 query 无法拆词 → sparse 结果为空,只剩 dense。改用 `pg_jieba`(见 `docs/interview-qa/01-retrieval.md` Q5)。
- embedding 维度不一致:query embedding 和存储 embedding 维度不匹配会导致 pgvector 报错或返回空。检查 `EMBEDDING_MODEL` 环境变量是否和 ingest 时一致。

**Step 2b: 如果 chunks 有内容但 grade 判 not relevant**

```
trace → grade span → output → relevant=False, reasoning=...
```

- 看 grader 的 reasoning:是 chunks 真的不相关,还是 grader 误判?
- 验证:`uv run python -c "from mvp_agentic_rag.agent.components import LLMDocGrader; ..."`(临时脚本)直接调 grader 测单个 chunk。
- 调整方向:降低 grader 的相关性阈值;或改进 chunk_size(太小导致语义碎片)。

**Step 3: 验证修复**

```bash
# 修复 ingest / 参数后重跑 eval
make eval
# 检查 kb-autoscaling / kb-pgvector 两个 case 是否通过
```

**Step 4: 补 golden case**

```jsonl
{"id":"<新case-id>","question":"<具体失败的 query>","must_include":["<期望命中的关键词>"],"expected_route":"kb_rag"}
```

追加到 `eval/golden/cases.jsonl`,commit,从此作为回归 case。

---

## 症状 2: 答案不接地 — 答案看起来是编造的,没有来自知识库的依据

### 症状表现
- answer 有内容,但包含知识库里没有的事实("幻觉")。
- grounding_check 判 grounded=False,或 ragas faithfulness 很低。

### 排查步骤

**Step 1: 看 Langfuse trace 的 generate 和 grounding_check span**

```
generate span:
  input: {query, chunks: [...]}
  output: {answer: "..."}

grounding_check span:
  input: {answer, chunks}
  output: {grounded: False}
```

**Step 2: 手动验证 chunks 和 answer 的关系**

把 generate span 里的 chunks 复制出来,检查 answer 中的每个关键主张是否能在 chunks 原文找到:
- 找不到来源 → 典型幻觉。
- 有来源但 grounder 误判 not grounded → grounder 阈值或 prompt 问题。

**Step 3: 区分幻觉来源**

| 现象 | 根因 | 修复方向 |
|---|---|---|
| chunks 相关但 answer 引入额外事实 | LLM 幻觉,generate prompt 约束不够 | 加强 system prompt 的"仅依据以下内容回答"约束;降低 temperature |
| chunks 本身有误/过时 | 知识库数据质量问题 | 更新/重新 ingest 文档;加文档时间戳过滤 |
| grounder 误判(chunks 里有答案但判 not grounded) | grounder 阈值或 prompt 问题 | 调整 grounder prompt;换 NLI 模型 |

**Step 4: 用 ragas faithfulness 定量验证**

```bash
# 需要 uv sync --extra eval 和有效 LLM key
uv run python -c "
from mvp_agentic_rag.eval.ragas_eval import evaluate_ragas
result = evaluate_ragas([{
    'question': '<问题>',
    'answer': '<你怀疑的答案>',
    'contexts': ['<chunk1>', '<chunk2>'],
}])
print(result)
"
```

faithfulness < 0.5 → 确认幻觉,找 generate prompt;faithfulness > 0.8 且 grounder=False → 找 grounder。

**Step 5: 回归**

```bash
make eval
# 确认 pass_rate 没下降
```

---

## 症状 3: 延迟高 — 用户等待超过预期(>10 秒)

### 症状表现
- 正常答案(内容正确)但响应时间明显变慢。
- 监控告警触发:`rag_llm_latency_seconds` P95 超阈值。

### 排查步骤

**Step 1: 看 /metrics 确认延迟分布**

```bash
curl http://localhost:8000/metrics | grep rag_llm_latency_seconds
```

- P50 正常、P99 高 → 偶发慢请求(长尾),可能是 rewrite 触发多次 LLM 调用。
- P50 也高 → 系统性问题,查 LLM provider / DB 连接。

**Step 2: 看 Langfuse trace 各 span 耗时**

Langfuse trace 的每个 span 都有 latency:
- `retrieve` span 慢(>1s) → pgvector ANN 查询慢,检查 HNSW index 是否建好:
  ```sql
  SELECT indexname FROM pg_indexes WHERE tablename='chunks';
  -- 应该看到 hnsw 索引
  ```
- `rerank` 慢 → 候选集太大(top-N 设置过高);换更快的 reranker 或缩小 N。
- `generate` span 慢 → LLM provider 慢,检查 provider 状态页;或 token 数过大(context 膨胀)。
- `generate` 被调用 **多次**(多个 generate span) → rewrite 触发了,看 max_rewrites 配置。

**Step 3: 检查是否有 rewrite 循环**

```
trace 中出现:retrieve → grade → rewrite → retrieve → grade → generate
```

`rag_llm_calls_total` 比同期请求数高出很多 → rewrite 循环频繁触发。
- 原因:grade prompt 太严格(总判 not relevant);或 chunk_size 太小导致 chunks 缺乏上下文。
- 修复:降低 grade 阈值,或增大 chunk_size,或直接降低 max_rewrites。

**Step 4: 检查 context 长度是否膨胀**

```
generate span → input → token count
```

token 数远超预期 → top-K 设置太大(rerank 后还是传了太多 chunks 给 LLM)。
- 修复:减小 rerank 后的 top-K(如从 10 降到 5);在 generator 里加 context 长度上限。

**Step 5: 临时缓解**

- 降低 LLM_TIMEOUT 让超时请求快速失败(trade accuracy for latency)。
- 切 fallback 模型(更小更快):设置 `LLM_MODEL_FALLBACK=gpt-4o-mini`。

**Step 6: 回归**

```bash
uv run pytest -q
# 确认测试全绿,改动未引入逻辑回归
make eval  # (配 key)确认 pass_rate 未下降
```

---

## 快查索引

| 症状 | 优先看 | 关键指标 / span |
|---|---|---|
| 答案为"依据不足" | retrieve span → chunks 是否为空 | `grade.relevant`, `chunks` list |
| 答案有幻觉 | generate span → answer vs chunks | `grounding_check.grounded`, ragas faithfulness |
| 延迟高 | /metrics + 各 span latency | `rag_llm_latency_seconds`, generate 被调次数 |
| 路由错误(应走 kb_rag 走了 web) | supervisor span → RouteDecision | `supervisor.output.route` |
| 工具报错 | web span / tool span | `rag_tool_errors_total` |
| CI eval 挂 | 看挂掉的 case id | `diff_reports` 输出 |

---

## 回归流程标准化

修复任何问题后,标准回归三步:

```bash
# 1. hermetic 测试(秒级,不需要 key)
uv run pytest -q

# 2. live eval(需要 .env key 和运行中的 DB)
make eval
# 看 pass_rate >= 0.9

# 3. 若发现新的失败 query,追加 golden case
echo '{"id":"<id>","question":"...","must_include":[...],"expected_route":"kb_rag"}' \
  >> eval/golden/cases.jsonl
git add eval/golden/cases.jsonl
git commit -m "eval: 补充 <症状描述> 回归 case"
```

**理论方法论参考**:`ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md`
