# 05 - Memory 搜索引擎：混合搜索、MMR 与时间衰减

> 存储只是基础，搜索才是 Memory 系统的核心价值。
> 本文剖析搜索管线的完整路径：查询扩展 → 向量/关键词并行搜索 → 混合合并 → MMR 去重 → 时间衰减。

---

## 搜索管线全景

```
用户查询: "上周讨论的数据库迁移方案"
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ search-manager.ts: getMemorySearchManager()                 │
│  · QMD 可用? → 用 QMD                                      │
│  · QMD 不可用? → 降级到 builtin (MemoryIndexManager)       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ query-expansion.ts: extractKeywords()                       │
│  · "上周讨论的数据库迁移方案"                                │
│  → ["讨论", "数据库", "迁移", "方案", "数据", "据库",       │
│     "迁移", "方案"]  (中文 bigram)                           │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
┌──────────────────┐   ┌──────────────────┐
│ searchVector()   │   │ searchKeyword()  │
│  sqlite-vec      │   │  FTS5 + BM25     │
│  余弦距离        │   │  全文匹配        │
│  → 语义相似      │   │  → 精确匹配      │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ hybrid.ts: mergeHybridResults()                             │
│  · 加权合并: 0.6 × vectorScore + 0.4 × textScore          │
│  · 同一分块的两个分数合并                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ temporal-decay.ts: applyTemporalDecay()                     │
│  · 提取日期（路径 or mtime）                                │
│  · 指数衰减: score × e^(-λ × age)                          │
│  · 半衰期默认 30 天                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ mmr.ts: mmrRerank()                                         │
│  · MMR = λ × relevance - (1-λ) × max_similarity            │
│  · Jaccard 相似度去重                                       │
│  · λ=0.7 (默认)                                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              最终搜索结果 (Top-K)
```

---

## 搜索后端选择：search-manager.ts

源码：`memory/search-manager.ts:1-269`

```typescript
export async function getMemorySearchManager(params: {
  cfg: OpenClawConfig;
  agentId: string;
}): Promise<MemorySearchManagerResult> {
  const resolved = resolveBackendConfig(params.cfg);

  // 1. 尝试 QMD（外部高性能索引）
  if (resolved.backend === "qmd" && resolved.qmd) {
    const qmd = await QmdMemoryManager.create(params);
    if (qmd) {
      // 包装 FallbackMemoryManager：QMD 失败自动降级
      return new FallbackMemoryManager({
        primary: qmd,
        fallbackFactory: () => MemoryIndexManager.get(params),
      });
    }
  }

  // 2. 降级到 builtin
  return await MemoryIndexManager.get(params);
}
```

### FallbackMemoryManager

```typescript
class FallbackMemoryManager implements MemorySearchManager {
  private active: MemorySearchManager;   // 当前活跃后端
  private failed = false;

  async search(query, opts?) {
    try {
      return await this.active.search(query, opts);
    } catch (err) {
      if (!this.failed) {
        // 首次失败：切换到 fallback
        this.failed = true;
        this.active = await this.fallbackFactory();
        return await this.active.search(query, opts);
      }
      throw err;
    }
  }
}
```

---

## 向量搜索：manager-search.ts

源码：`memory/manager-search.ts:1-191`

```typescript
export async function searchVector(params: {
  db: DatabaseSync;
  queryVec: number[];
  limit: number;
  providerModel: string;
}): Promise<SearchRowResult[]> {
  // 使用 sqlite-vec 扩展的余弦距离
  const rows = params.db.prepare(`
    SELECT c.id, c.path, c.start_line, c.end_line, c.text, c.source,
           vec_distance_cosine(v.embedding, ?) AS dist
      FROM chunks_vec v
      JOIN chunks c ON c.id = v.id
     WHERE c.model = ?
     ORDER BY dist ASC
     LIMIT ?
  `).all(
    vectorToBlob(params.queryVec),  // Float32Array → Buffer
    params.providerModel,
    params.limit,
  );

  // 距离 → 相似度 (1 - distance)
  return rows.map(r => ({
    ...r,
    score: 1 - r.dist,  // dist ∈ [0, 2], score ∈ [-1, 1]
  }));
}
```

**降级路径**：如果 sqlite-vec 扩展不可用（某些 Node 发行版不支持），降级到内存计算：

```typescript
// 从 DB 加载所有分块的嵌入，在内存中计算余弦相似度
const chunks = listChunks();
return chunks
  .map(chunk => ({
    ...chunk,
    score: cosineSimilarity(queryVec, parseEmbedding(chunk.embedding)),
  }))
  .filter(e => Number.isFinite(e.score))
  .sort((a, b) => b.score - a.score)
  .slice(0, limit);
```

---

## 关键词搜索：FTS5 + BM25

```typescript
export async function searchKeyword(params: {
  db: DatabaseSync;
  query: string;
  limit: number;
  buildFtsQuery: (raw: string) => string | null;
  bm25RankToScore: (rank: number) => number;
}): Promise<SearchRowResult[]> {
  const ftsQuery = params.buildFtsQuery(params.query);
  if (!ftsQuery) return [];

  const rows = params.db.prepare(`
    SELECT id, path, source, start_line, end_line, text,
           bm25(chunks_fts) AS rank
      FROM chunks_fts
     WHERE chunks_fts MATCH ? AND model = ?
     ORDER BY rank ASC
     LIMIT ?
  `).all(ftsQuery, providerModel, limit);

  return rows.map(r => ({
    ...r,
    score: params.bm25RankToScore(r.rank),
  }));
}
```

### FTS Query 构建

```typescript
// hybrid.ts
export function buildFtsQuery(raw: string): string | null {
  // 提取所有 Unicode 单词
  const tokens = raw.match(/[\p{L}\p{N}_]+/gu)
    ?.map(t => t.trim())
    .filter(Boolean) ?? [];

  if (tokens.length === 0) return null;

  // 构建 AND 查询: "word1" AND "word2"
  const quoted = tokens.map(t => `"${t.replaceAll('"', '')}"`);
  return quoted.join(" AND ");
}
```

### BM25 分数归一化

```typescript
export function bm25RankToScore(rank: number): number {
  if (!Number.isFinite(rank)) return 1 / 1000;
  if (rank < 0) {
    // FTS5 的 rank 值: 负数 = 更相关（绝对值越大越好）
    const relevance = -rank;
    return relevance / (1 + relevance);  // Sigmoid 归一化到 [0, 1)
  }
  return 1 / (1 + rank);  // 正数 = 不太相关
}
```

---

## 混合合并：hybrid.ts

源码：`memory/hybrid.ts:1-155`

```typescript
export async function mergeHybridResults(params: {
  vector: HybridVectorResult[];
  keyword: HybridKeywordResult[];
  vectorWeight: number;   // 默认 0.6
  textWeight: number;     // 默认 0.4
  mmr?: Partial<MMRConfig>;
  temporalDecay?: Partial<TemporalDecayConfig>;
}): Promise<HybridResult[]> {

  // Step 1: 按分块 ID 合并
  const byId = new Map<string, MergedEntry>();

  for (const r of params.vector) {
    byId.set(r.id, { ...r, vectorScore: r.vectorScore, textScore: 0 });
  }

  for (const r of params.keyword) {
    const existing = byId.get(r.id);
    if (existing) {
      // 同一分块同时出现在向量和关键词结果中 → 合并分数
      existing.textScore = r.textScore;
      if (r.snippet) existing.snippet = r.snippet;  // 关键词匹配的 snippet 更好
    } else {
      byId.set(r.id, { ...r, vectorScore: 0, textScore: r.textScore });
    }
  }

  // Step 2: 加权求和
  const merged = Array.from(byId.values()).map(entry => ({
    ...entry,
    score: params.vectorWeight * entry.vectorScore +
           params.textWeight * entry.textScore,
  }));

  // Step 3: 时间衰减
  const decayed = await applyTemporalDecayToHybridResults({
    results: merged,
    temporalDecay: params.temporalDecay,
  });

  // Step 4: MMR 去重（如果启用）
  const sorted = decayed.sort((a, b) => b.score - a.score);
  if (params.mmr?.enabled) {
    return applyMMRToHybridResults(sorted, params.mmr);
  }

  return sorted;
}
```

**为什么是 0.6/0.4？**
- 向量搜索擅长**语义理解**（"数据库迁移" ≈ "DB migration"）
- 关键词搜索擅长**精确匹配**（用户说的具体术语、名字、日期）
- 6:4 的比例偏向语义，但不忽视精确匹配

---

## 时间衰减：temporal-decay.ts

源码：`memory/temporal-decay.ts:1-167`

### 衰减模型

```typescript
// 指数衰减: multiplier = e^(-λ × age)
// 其中 λ = ln(2) / halfLifeDays

export function calculateTemporalDecayMultiplier(params: {
  ageInDays: number;
  halfLifeDays: number;   // 默认 30 天
}): number {
  const lambda = Math.LN2 / params.halfLifeDays;  // λ = ln(2) / 30
  const clampedAge = Math.max(0, params.ageInDays);
  return Math.exp(-lambda * clampedAge);
}

// 在半衰期（30天）时:
// multiplier = e^(-ln(2)) = 0.5
// 即 30 天前的记忆分数减半
```

**衰减曲线**：

```
score multiplier
  1.0 ┤ ████████
  0.9 ┤ ██████████
  0.8 ┤ ████████████
  0.7 ┤ ██████████████
  0.6 ┤ ████████████████
  0.5 ┤ ██████████████████     ← 30 天（半衰期）
  0.4 ┤ ████████████████████
  0.3 ┤ ██████████████████████
  0.25┤ ███████████████████████ ← 60 天
  0.2 ┤
      └────┬────┬────┬────┬────
           0   15   30   45   60  (天)
```

### 日期提取

```typescript
// 从文件路径提取日期
function parseMemoryDateFromPath(filePath: string): Date | null {
  // 匹配 memory/YYYY-MM-DD.md
  const match = /(?:^|\/)memory\/(\d{4})-(\d{2})-(\d{2})\.md$/.exec(filePath);
  if (!match) return null;
  return new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
}

// "常青"记忆不衰减
function isEvergreenMemoryPath(filePath: string): boolean {
  // MEMORY.md 和 非日期命名的 memory/*.md
  return filePath === "MEMORY.md" || !DATED_MEMORY_PATH_RE.test(filePath);
}
```

**关键设计**：
- 日期命名的文件（`memory/2026-03-15.md`）→ 应用衰减
- 非日期命名的文件（`memory/project-architecture.md`）→ 常青，不衰减
- 降级策略：路径没有日期 → 用文件 mtime

### 应用衰减

```typescript
export async function applyTemporalDecayToHybridResults(params) {
  const config = { ...DEFAULT_TEMPORAL_DECAY_CONFIG, ...params.temporalDecay };
  if (!config.enabled) return [...params.results];

  const nowMs = params.nowMs ?? Date.now();

  return Promise.all(
    params.results.map(async (entry) => {
      const timestamp = await extractTimestamp(entry);
      if (!timestamp) return entry;  // 无法提取日期 → 不衰减

      const ageInDays = (nowMs - timestamp.getTime()) / (24 * 60 * 60 * 1000);
      const decayedScore = entry.score * calculateTemporalDecayMultiplier({
        ageInDays,
        halfLifeDays: config.halfLifeDays,
      });

      return { ...entry, score: decayedScore };
    }),
  );
}
```

---

## MMR 多样性重排：mmr.ts

源码：`memory/mmr.ts:1-214`

### MMR 算法（Carbonell & Goldstein, 1998）

核心公式：

```
MMR(d) = λ × Relevance(d) - (1-λ) × max[Similarity(d, s) for s in Selected]
```

- `λ` 接近 1 → 偏向相关性（可能有很多相似结果）
- `λ` 接近 0 → 偏向多样性（可能选到不太相关的结果）
- 默认 `λ = 0.7` → 平衡

### 实现

```typescript
export function mmrRerank<T extends MMRItem>(
  items: T[],
  config: Partial<MMRConfig> = {},
): T[] {
  const { enabled = false, lambda = 0.7 } = config;
  if (!enabled || items.length <= 1) return [...items];

  const clampedLambda = Math.max(0, Math.min(1, lambda));

  // 预计算: 对每个 item tokenize
  const tokenCache = new Map<string, Set<string>>();
  for (const item of items) {
    tokenCache.set(item.id, tokenize(item.content));
  }

  // 归一化分数到 [0, 1]
  const maxScore = Math.max(...items.map(i => i.score));
  const minScore = Math.min(...items.map(i => i.score));
  const scoreRange = maxScore - minScore;
  const normalize = (score: number) =>
    scoreRange === 0 ? 1 : (score - minScore) / scoreRange;

  // 贪心选择
  const selected: T[] = [];
  const remaining = new Set(items);

  while (remaining.size > 0) {
    let bestItem: T | null = null;
    let bestMMRScore = -Infinity;

    for (const candidate of remaining) {
      const relevance = normalize(candidate.score);

      // 与已选集合中最相似的项的 Jaccard 相似度
      const maxSim = maxSimilarityToSelected(candidate, selected, tokenCache);

      // MMR 公式
      const mmrScore = clampedLambda * relevance - (1 - clampedLambda) * maxSim;

      if (mmrScore > bestMMRScore) {
        bestMMRScore = mmrScore;
        bestItem = candidate;
      }
    }

    if (bestItem) {
      selected.push(bestItem);
      remaining.delete(bestItem);
    } else {
      break;
    }
  }

  return selected;
}
```

### Jaccard 相似度

```typescript
function jaccardSimilarity(setA: Set<string>, setB: Set<string>): number {
  if (setA.size === 0 && setB.size === 0) return 1;
  if (setA.size === 0 || setB.size === 0) return 0;

  let intersectionSize = 0;
  const smaller = setA.size <= setB.size ? setA : setB;
  const larger = setA.size <= setB.size ? setB : setA;

  for (const token of smaller) {
    if (larger.has(token)) intersectionSize++;
  }

  const unionSize = setA.size + setB.size - intersectionSize;
  return intersectionSize / unionSize;
}
```

**为什么用 Jaccard 而不是余弦？** MMR 在这里是对搜索结果做去重，输入是文本分块（不是向量）。Jaccard 直接在 token 集合上计算，不需要嵌入，速度更快。

### MMR 的实际效果

假设搜索 "数据库迁移"，返回 5 个结果：

```
无 MMR:
1. "PostgreSQL 迁移脚本 v1" (score: 0.92)
2. "PostgreSQL 迁移脚本 v2" (score: 0.91)  ← 和 1 几乎一样
3. "PostgreSQL 迁移回滚" (score: 0.88)     ← 和 1、2 很像
4. "MySQL 迁移策略" (score: 0.85)
5. "迁移测试计划" (score: 0.83)

有 MMR (λ=0.7):
1. "PostgreSQL 迁移脚本 v1" (mmr: 0.92)
2. "MySQL 迁移策略" (mmr: 0.78)           ← 提前！和 1 不像
3. "迁移测试计划" (mmr: 0.71)             ← 提前！
4. "PostgreSQL 迁移脚本 v2" (mmr: 0.65)   ← 降级（和 1 太像）
5. "PostgreSQL 迁移回滚" (mmr: 0.60)
```

---

## 查询扩展：query-expansion.ts

源码：`memory/query-expansion.ts:1-810`

### 多语言 Tokenizer

```typescript
function tokenize(text: string): string[] {
  const tokens: string[] = [];
  const segments = text.toLowerCase().split(/[\s\p{P}]+/u).filter(Boolean);

  for (const segment of segments) {

    // 日文: 汉字/假名/ASCII 分离
    if (/[\u3040-\u30ff]/.test(segment)) {
      const jpParts = segment.match(
        /[a-z0-9_]+|[\u30a0-\u30ffー]+|[\u4e00-\u9fff]+|[\u3040-\u309f]{2,}/g
      ) ?? [];
      for (const part of jpParts) {
        if (/^[\u4e00-\u9fff]+$/.test(part)) {
          tokens.push(part);
          // 汉字 bigram
          for (let i = 0; i < part.length - 1; i++) {
            tokens.push(part[i] + part[i + 1]);
          }
        } else {
          tokens.push(part);
        }
      }
    }

    // 中文: 字符 unigram + bigram
    else if (/[\u4e00-\u9fff]/.test(segment)) {
      const chars = Array.from(segment).filter(c => /[\u4e00-\u9fff]/.test(c));
      tokens.push(...chars);  // unigram
      for (let i = 0; i < chars.length - 1; i++) {
        tokens.push(chars[i] + chars[i + 1]);  // bigram
      }
    }

    // 韩文: 尾缀助词剥离
    else if (/[\uac00-\ud7af]/.test(segment)) {
      const stem = stripKoreanTrailingParticle(segment);
      if (!STOP_WORDS_KO.has(segment)) {
        tokens.push(segment);
      }
      if (stem && isUsefulKoreanStem(stem)) {
        tokens.push(stem);
      }
    }

    // 英文和其他
    else {
      tokens.push(segment);
    }
  }

  return tokens;
}
```

### 中文分词示例

```
输入: "上周讨论的数据库迁移方案"

分词过程:
  "上" → unigram
  "周" → unigram
  "讨" → unigram
  "论" → unigram
  "的" → unigram
  "数" → unigram
  "据" → unigram
  "库" → unigram
  "迁" → unigram
  "移" → unigram
  "方" → unigram
  "案" → unigram
  "上周" → bigram
  "讨论" → bigram
  "数据" → bigram
  "据库" → bigram
  "迁移" → bigram
  "方案" → bigram

过滤停用词 ("的", "上", "周" 等单字):
  → ["讨论", "数据", "据库", "迁移", "方案", "数据库"]
```

**为什么用 bigram 而不是分词器？**
- 不依赖外部分词库（jieba 等），零依赖
- bigram 能覆盖大部分词语（"数据库" = "数据" + "据库"）
- 对于搜索场景，recall 比 precision 更重要

### 关键词提取

```typescript
export function extractKeywords(query: string): string[] {
  const tokens = tokenize(query);
  const keywords: string[] = [];
  const seen = new Set<string>();

  for (const token of tokens) {
    if (isQueryStopWordToken(token)) continue;  // 停用词过滤
    if (!isValidKeyword(token)) continue;        // 有效性检查
    if (seen.has(token)) continue;               // 去重

    seen.add(token);
    keywords.push(token);
  }
  return keywords;
}

function isValidKeyword(token: string): boolean {
  if (!token) return false;
  if (/^[a-zA-Z]+$/.test(token) && token.length < 3) return false;  // 太短的英文
  if (/^\d+$/.test(token)) return false;                             // 纯数字
  if (/^[\p{P}\p{S}]+$/u.test(token)) return false;                 // 纯标点
  return true;
}
```

### 停用词（8+ 语言）

```typescript
const STOP_WORDS_EN = new Set([
  "a", "an", "the", "is", "are", "was", "were", "be", "been",
  "do", "does", "did", "have", "has", "had", "will", "would",
  "can", "could", "should", "may", "might", "shall", "must",
  "i", "me", "my", "you", "your", "he", "she", "it", "we", "they",
  "this", "that", "these", "those", "what", "which", "who", "whom",
  "how", "when", "where", "why", "not", "no", "nor", "but", "or",
  "and", "if", "then", "so", "very", "just", "about", "also",
  // ...更多
]);

const STOP_WORDS_ZH = new Set([
  "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
  "都", "一", "个", "上", "也", "很", "到", "说", "要", "去",
  // ...更多
]);

const STOP_WORDS_KO = new Set(["은", "는", "이", "가", "을", "를", ...]);
const STOP_WORDS_JA = new Set(["の", "に", "は", "を", "た", "が", ...]);
```

---

## QMD 集成：qmd-manager.ts

源码：`memory/qmd-manager.ts:1-2069`

QMD 是一个外部 CLI 工具，提供高性能的全文 + 向量搜索。OpenClaw 通过子进程调用它。

```typescript
// 调用 QMD CLI
const result = await spawnQmdProcess({
  command: "search",
  args: ["--query", query, "--limit", String(limit), "--json"],
  timeout: 5000,
});

// 解析 JSON 输出
const parsed = parseQmdOutput(result.stdout);
return parsed.results.map(r => ({
  path: r.path,
  startLine: r.start_line,
  endLine: r.end_line,
  score: r.score,
  snippet: r.snippet,
  source: r.source,
}));
```

**QMD vs Builtin**：
- QMD 有自己的索引和搜索引擎，性能更好
- 支持多集合（memory + sessions + custom）
- 但需要额外安装
- Builtin 作为 QMD 不可用时的降级方案

---

## 完整搜索示例

查询：`"上周和 Sarah 讨论的 API 重构方案"`

```
1. 查询扩展:
   extractKeywords() → ["sarah", "讨论", "api", "重构", "方案"]

2. 嵌入查询向量:
   provider.embed("上周和 Sarah 讨论的 API 重构方案") → queryVec[768]

3. 并行搜索:
   searchVector(queryVec, limit=20):
     → [{ id: "c1", path: "memory/2026-03-14.md", score: 0.87 },
        { id: "c5", path: "memory/api-design.md", score: 0.82 },
        { id: "c3", path: "memory/2026-03-10.md", score: 0.79 },
        ...]

   searchKeyword("sarah AND api AND 重构", limit=20):
     → [{ id: "c1", path: "memory/2026-03-14.md", score: 0.91 },
        { id: "c7", path: "sessions/abc.jsonl", score: 0.75 },
        ...]

4. 混合合并 (vectorWeight=0.6, textWeight=0.4):
   c1: 0.6 × 0.87 + 0.4 × 0.91 = 0.886  ← 两个搜索都命中，分数最高
   c5: 0.6 × 0.82 + 0.4 × 0    = 0.492
   c7: 0.6 × 0    + 0.4 × 0.75 = 0.300
   c3: 0.6 × 0.79 + 0.4 × 0    = 0.474

5. 时间衰减 (halfLife=30 days):
   c1 (2026-03-14, 7 天前): 0.886 × e^(-0.023 × 7)  = 0.886 × 0.85 = 0.753
   c5 (evergreen):          0.492 × 1.0               = 0.492
   c3 (2026-03-10, 11 天前): 0.474 × e^(-0.023 × 11) = 0.474 × 0.78 = 0.370
   c7 (session, 5 天前):    0.300 × e^(-0.023 × 5)   = 0.300 × 0.89 = 0.267

6. MMR 重排 (λ=0.7):
   → c1 (0.753) — 选中（最高分）
   → c5 (0.492) — 选中（和 c1 内容不同）
   → c3 (0.370) — 降级（和 c1 来自相似日期，内容重叠）
   → c7 (0.267) — 选中（session 来源，角度不同）

7. 最终结果:
   [c1: memory/2026-03-14.md:15-32 (0.753),
    c5: memory/api-design.md:1-18 (0.492),
    c7: sessions/abc.jsonl:... (0.267)]
```

---

## 设计洞察

### 混合搜索为什么比单一搜索好？

| 查询类型 | 向量搜索 | 关键词搜索 | 混合搜索 |
|----------|---------|-----------|---------|
| "数据库迁移策略" | ✓ 语义理解 | ✓ 精确匹配 | ✓✓ |
| "Sarah 说的那个想法" | ✓ 理解"想法"的语义 | ✓ 精确匹配 "Sarah" | ✓✓ |
| "DB migration" (英文查中文) | ✓ 跨语言语义 | ✗ 完全无法匹配 | ✓ |
| "JIRA-1234" (工单号) | ✗ 语义无意义 | ✓ 精确匹配 | ✓ |

**向量搜索和关键词搜索是互补的**，混合搜索取两者之长。

### 时间衰减的哲学

不是所有记忆都应该永久保鲜。30 天前的讨论笔记可能已经过时了，但架构文档（常青记忆）应该永远保持高权重。OpenClaw 通过**文件命名**来区分：
- `memory/2026-03-14.md` → 日期记忆，会衰减
- `memory/architecture.md` → 常青记忆，不衰减

这是一个简洁有效的启发式。

### MMR 的成本

MMR 是 O(n²) 的（每选一个 item，要和所有已选 item 比较）。但在 Memory 搜索场景下：
- n 通常 < 50（搜索返回的 top-K）
- tokenize 和 Jaccard 都是简单的集合操作
- 毫秒级完成，不是瓶颈
