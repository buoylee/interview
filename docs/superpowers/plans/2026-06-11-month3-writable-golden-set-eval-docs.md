# 月 3 可写部分:语料扩充 + golden set 扩充 + 07/01 评估工程节

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 MVP eval 的「可写地基」铺好:知识库语料从 11 行扩到能支撑真实评估的规模、golden set 从 4 条扩到 20+ 条、07/01 评估文档补上工具对比 + 可直接使用的完整 judge prompt。真实跑分(`make eval` 报告、judge 校准数字)仍属月 3 主线,待用户 key,本计划不含。

**Architecture:** GoldenCase schema(`eval/dataset.py`)与确定性检查(`eval/checks.py`:must_include/route/citations/refusal,拒答标记 `依据不足`/`未找到足够依据`)已存在且不动;新 case 必须与扩充后语料严格对齐(must_include 的词必须是正确答案必然包含的、expected_citation_docs 必须真实存在)。语料是事实性技术文档,内容必须正确——这是面试作品,错误事实是硬伤。

**Tech Stack:** 纯 markdown/jsonl авторинг + 一条 load_golden 冒烟测试。

---

## 上位文档
- spec 决策 4 + 第九节(月 3);MVP eval 代码:`src/mvp_agentic_rag/eval/{dataset,checks}.py`
- 现状:`eval/golden/cases.jsonl` 4 条;`sample_docs/` 仅 kubernetes.md(6 行)+ postgres.md(5 行)

## 文件结构
```
ai/langchain/mvp-agentic-rag/
├─ sample_docs/
│  ├─ kubernetes.md      (扩:~50 行,K8s 探针/HPA/Service/滚动发布)
│  ├─ postgres.md        (扩:~50 行,pgvector 索引/锁/全文检索/连接池)
│  ├─ docker.md          (新:~40 行,镜像分层/网络/volume/compose)
│  └─ redis.md           (新:~40 行,数据结构/过期/持久化/缓存一致)
├─ eval/golden/cases.jsonl (4 → 20+ 条)
└─ tests/test_eval_dataset.py (新:load_golden 解析全部 case + 与语料一致性断言)

ai/ml-to-llm-roadmap/07-evaluation-safety-production/
└─ 01-llm-evaluation-judge.md (追加:评估工程工具对比节 + 完整 judge prompt 示例 + 校准操作步骤〔数字待实测〕)
```

### Task A: 语料扩充(事实必须正确)
- [ ] 扩写/新建上述 4 个 md:每篇 8-12 段、有标题层级,内容为稳定的工程事实(探针类型、HNSW vs IVFFlat 取舍、镜像分层、Redis 过期策略等),不写版本敏感的具体数字
- [ ] 同步检查引用了 sample_docs 文件清单的文档(`grep -rn "kubernetes.md" ai/agent-loop-lab/ --include=*.md`)并更新提及处
- [ ] Commit:`mvp-agentic-rag: 知识库语料扩充(k8s/postgres/docker/redis)`

### Task B: golden set 扩充 + 冒烟测试
- [ ] cases.jsonl 扩到 20+ 条,覆盖:每文档 2-3 条直答(must_include 用语料中必然出现在正确答案里的词,注意大小写)、2 条跨文档、3 条域外→`expected_route: "web"`、3 条应拒答(敏感/无依据,`should_refuse: true`)、2 条模糊问题(检验改写,只设 route 不设 must_include)
- [ ] 新 tests/test_eval_dataset.py:load_golden 全部解析成功;每条 expected_citation_docs 的文件真实存在于 sample_docs;id 唯一
- [ ] `uv run pytest tests/test_eval_dataset.py -v` 通过;全套无新增失败
- [ ] Commit:`mvp-agentic-rag: golden set 扩到 20+ 条 + 数据集一致性测试`

### Task C: 07/01 评估工程节 + judge prompt
- [ ] `01-llm-evaluation-judge.md` 文末追加两节:
  1. **「评估工程:工具怎么选(2026)」**:ragas(RAG 三元组指标,MVP 可选依赖已接)/ deepeval / promptfoo(配置驱动回归)/ LangSmith vs Langfuse(平台型,datasets+annotation)/ 自建 checks(MVP 的 `eval/checks.py` 就是)对比表 + 选型一句话;只写稳定事实,不写价格/版本号
  2. **「实战锚点(2026-06)」**:链接 MVP eval 闭环代码(checks/dataset/runner/report + golden 20+ 条)、给出**完整可用的中文 judge prompt 示例**(correctness/groundedness/helpfulness/safety 四维 1-5 分 + 输出 JSON schema + 2 个 few-shot 锚定样例),judge 校准操作步骤(抽样人工复核→一致率→修 rubric),所有跑分数字〔待实测:make eval 后回填〕
- [ ] 链接校验;该文件有未提交用户改动则 BLOCKED
- [ ] Commit:`ml-to-llm-roadmap: 07/01 评估工程工具对比 + judge prompt 示例 + 锚点`

## 验收
- [ ] 新语料事实正确(review 逐条核)、case 与语料对齐(测试保证 citation 文件存在;must_include 词在对应文档中出现过)
- [ ] 现有测试零回归;无编造数字
