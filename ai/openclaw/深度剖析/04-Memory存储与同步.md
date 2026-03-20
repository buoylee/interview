# 04 - Memory 存储与同步：从文件到向量数据库

> OpenClaw 的 Memory 系统让 Agent 拥有跨会话的持久记忆。
> 本文剖析数据存储层：SQLite schema、文件监听、Markdown 分块、嵌入生成与缓存。

---

## 架构总览

```
memory/*.md 文件  +  session transcript (JSONL)
       │                        │
       ▼                        ▼
  chokidar 监听            transcript 事件
       │                        │
       └──────── 触发 sync ─────┘
                    │
                    ▼
           ┌── 变更检测 ──┐
           │ (hash 对比)   │
           ▼              ▼
     新增/修改文件    删除文件
           │              │
           ▼              ▼
    chunkMarkdown()   从 DB 删除
           │
           ▼
    嵌入生成 (OpenAI/Gemini/Voyage/Ollama)
           │
           ├── 缓存命中 → 直接使用
           └── 缓存未命中 → API 调用 → 存入缓存
                    │
                    ▼
              SQLite 写入
           ├── chunks 表 (文本 + 嵌入)
           ├── chunks_vec (向量索引)
           └── chunks_fts (全文索引)
```

---

## SQLite Schema

源码：`memory/memory-schema.ts:1-96`

```sql
-- 元数据表：跟踪索引状态
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);

-- 文件表：变更检测
CREATE TABLE IF NOT EXISTS files (
  path TEXT PRIMARY KEY,
  hash TEXT NOT NULL,           -- SHA-256 内容哈希
  mtime INTEGER NOT NULL,       -- 修改时间
  size INTEGER NOT NULL,         -- 文件大小
  source TEXT DEFAULT 'memory'   -- 'memory' 或 'sessions'
);
CREATE INDEX idx_files_source ON files(source);

-- 分块表：核心存储
CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  source TEXT DEFAULT 'memory',
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  text TEXT NOT NULL,
  hash TEXT NOT NULL,            -- 分块内容哈希
  model TEXT,                    -- 嵌入模型标识
  embedding TEXT,                -- 嵌入向量 (JSON)
  updated_at INTEGER
);
CREATE INDEX idx_chunks_path ON chunks(path);
CREATE INDEX idx_chunks_source ON chunks(source);
CREATE INDEX idx_chunks_updated ON chunks(updated_at);

-- 向量索引：sqlite-vec 扩展
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0 (
  id TEXT PRIMARY KEY,
  embedding FLOAT[{dimensions}]  -- 维度由模型决定 (768/1536/3072)
);

-- 全文索引：FTS5
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5 (
  id, path, source, text, model,
  content=chunks,
  content_rowid=rowid
);

-- 嵌入缓存：避免重复 API 调用
CREATE TABLE IF NOT EXISTS embedding_cache (
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  provider_key TEXT NOT NULL,
  hash TEXT NOT NULL,             -- 文本哈希
  embedding TEXT NOT NULL,        -- 嵌入向量 (JSON)
  updated_at INTEGER,
  PRIMARY KEY (provider, model, provider_key, hash)
);
```

**设计要点**：
- `chunks` + `chunks_vec` + `chunks_fts` 三表联合，一份数据支持向量搜索和全文搜索
- `embedding_cache` 按 `(provider, model, provider_key, hash)` 缓存，切换模型不丢缓存
- `files.hash` 做增量检测，只处理实际变更的文件

---

## 文件监听与同步：manager-sync-ops.ts

源码：`memory/manager-sync-ops.ts:1-1391`

### chokidar 文件监听

```typescript
// manager-sync-ops.ts:377-432
private setupFileWatcher() {
  const watcher = chokidar.watch(this.memoryDir, {
    ignoreInitial: true,
    ignored: [
      /\.git/,
      /node_modules/,
      /__pycache__/,
      /\.venv/,
      // ... 更多忽略规则
    ],
    // 防抖
    awaitWriteFinish: {
      stabilityThreshold: 500,
      pollInterval: 100,
    },
  });

  watcher.on("change", (path) => this.markDirty("memory"));
  watcher.on("add", (path) => this.markDirty("memory"));
  watcher.on("unlink", (path) => this.markDirty("memory"));
}
```

### Session Transcript 增量跟踪

```typescript
// manager-sync-ops.ts:450-604
private async processSessionDeltaBatch() {
  // Session 文件是 JSONL 格式，增量追加
  // 跟踪 bytes/message count 变化

  const delta = this.sessionDeltaTracker.flush();
  // 只有变化超过阈值才触发 sync
  if (delta.bytesAdded > 100 * 1024 || delta.messagesAdded > 50) {
    this.markDirty("sessions");
  }
}
```

### 同步算法

```typescript
// manager-sync-ops.ts:935-1061
protected async runSync(params?) {
  // Step 1: 是否需要全量重建？
  const meta = this.readMeta();
  const needsFullReindex =
    !meta ||                                      // 首次运行
    meta.model !== this.provider.model ||          // 嵌入模型变了
    meta.provider !== this.provider.id ||          // 嵌入 provider 变了
    meta.chunkTokens !== this.settings.chunking.tokens ||   // 分块参数变了
    meta.chunkOverlap !== this.settings.chunking.overlap;

  // Step 2: 全量重建或增量同步
  if (needsFullReindex) {
    await this.runSafeReindex();  // 原子操作
  } else {
    // 增量同步
    if (this.isDirty("memory")) {
      await this.syncMemoryFiles({ needsFullReindex: false });
    }
    if (this.isDirty("sessions")) {
      await this.syncSessionFiles({ needsFullReindex: false });
    }
  }

  // Step 3: 清理嵌入缓存
  this.pruneEmbeddingCacheIfNeeded();
}
```

### 增量同步：文件级

```typescript
private async syncMemoryFiles(params: { needsFullReindex: boolean }) {
  // 1. 列出 memory/ 下所有 .md 文件
  const diskFiles = await listMemoryFiles(this.memoryDir);

  // 2. 去重（symlink → realpath）
  const uniqueFiles = deduplicateByRealpath(diskFiles);

  // 3. 对比数据库中的记录
  for (const file of uniqueFiles) {
    const dbFile = this.db.getFile(file.path);
    const currentHash = hashText(await fs.readFile(file.path, "utf-8"));

    if (!dbFile) {
      // 新文件 → 分块 + 嵌入 + 插入
      await this.indexFile(file.path, currentHash);
    } else if (dbFile.hash !== currentHash) {
      // 文件变了 → 删除旧分块 + 重新索引
      this.db.deleteChunksForFile(file.path);
      await this.indexFile(file.path, currentHash);
    }
    // hash 相同 → 跳过
  }

  // 4. 检查已删除的文件
  const dbPaths = this.db.listFilePaths("memory");
  for (const dbPath of dbPaths) {
    if (!diskFileSet.has(dbPath)) {
      this.db.deleteChunksForFile(dbPath);
      this.db.deleteFile(dbPath);
    }
  }
}
```

### 安全重建

当嵌入模型或分块参数变化时，需要全量重建。但重建过程中不能中断搜索服务：

```typescript
// manager-sync-ops.ts:1145-1253
private async runSafeReindex() {
  const tempDbPath = `${this.dbPath}.tmp.${Date.now()}`;
  const backupPath = `${this.dbPath}.backup`;

  try {
    // 1. 创建临时数据库
    const tempDb = createDatabase(tempDbPath);
    initializeSchema(tempDb);

    // 2. 从旧数据库迁移嵌入缓存（避免重复 API 调用）
    if (this.db) {
      seedEmbeddingCacheFrom(this.db, tempDb);
    }

    // 3. 在临时数据库中构建新索引
    await this.buildFullIndex(tempDb);

    // 4. 原子交换：旧 DB → backup, 临时 DB → 正式
    this.closeDb();
    await fs.rename(this.dbPath, backupPath);
    await fs.rename(tempDbPath, this.dbPath);
    this.openDb();

    // 5. 清理 backup
    await fs.unlink(backupPath).catch(() => {});

  } catch (err) {
    // 回滚：恢复 backup
    if (await fileExists(backupPath)) {
      await fs.rename(backupPath, this.dbPath);
    }
    await fs.unlink(tempDbPath).catch(() => {});
    this.openDb();
    throw err;
  }
}
```

**这是一个经典的"蓝绿部署"模式**：在临时数据库构建完成后才切换，失败自动回滚。

---

## Markdown 分块：internal.ts

源码：`memory/internal.ts:1-482`

### 分块算法

```typescript
// internal.ts
export function chunkMarkdown(
  content: string,
  chunking: { tokens: number; overlap: number },
): MemoryChunk[] {
  const maxChars = Math.max(32, chunking.tokens * 4);  // 1 token ≈ 4 chars
  const overlapChars = Math.max(0, chunking.overlap * 4);
  const lines = content.split("\n");
  const chunks: MemoryChunk[] = [];

  let current: Array<{ line: string; lineNo: number }> = [];
  let currentChars = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? "";
    const lineNo = i + 1;
    const lineSize = line.length + 1;  // +1 for \n

    // 超过最大字符数 → flush 当前块
    if (currentChars + lineSize > maxChars && current.length > 0) {
      flush();          // 写入 chunks
      carryOverlap();   // 保留末尾 overlap 部分
    }

    current.push({ line, lineNo });
    currentChars += lineSize;
  }
  flush();  // 最后一块
  return chunks;
}
```

**Overlap 机制**：

```typescript
const carryOverlap = () => {
  if (overlapChars <= 0 || current.length === 0) {
    current = [];
    currentChars = 0;
    return;
  }
  // 从末尾往前保留 overlapChars 字符
  let acc = 0;
  const kept: typeof current = [];
  for (let i = current.length - 1; i >= 0; i--) {
    acc += current[i].line.length + 1;
    kept.unshift(current[i]);
    if (acc >= overlapChars) break;
  }
  current = kept;
  currentChars = kept.reduce((sum, e) => sum + e.line.length + 1, 0);
};
```

**为什么需要 overlap？** 如果一个概念跨越两个分块的边界，overlap 确保两个分块都包含这个概念的一部分，搜索时不会遗漏。

### 哈希与相似度

```typescript
// SHA-256 哈希
export function hashText(value: string): string {
  return crypto.createHash("sha256").update(value).digest("hex");
}

// 余弦相似度（向量搜索的后备方案）
export function cosineSimilarity(a: number[], b: number[]): number {
  const len = Math.min(a.length, b.length);
  let dot = 0, normA = 0, normB = 0;

  for (let i = 0; i < len; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}
```

---

## 嵌入生成与缓存：manager-embedding-ops.ts

源码：`memory/manager-embedding-ops.ts:1-925`

### Token 预算分批

```typescript
// manager-embedding-ops.ts
private buildEmbeddingBatches(chunks: MemoryChunk[]): MemoryChunk[][] {
  const MAX_BATCH_TOKENS = 8000;
  const batches: MemoryChunk[][] = [];
  let current: MemoryChunk[] = [];
  let currentTokens = 0;

  for (const chunk of chunks) {
    const estimate = estimateStructuredEmbeddingInputBytes(chunk.embeddingInput);
    const wouldExceed = current.length > 0 && currentTokens + estimate > MAX_BATCH_TOKENS;
    if (wouldExceed) {
      batches.push(current);
      current = [];
      currentTokens = 0;
    }
    current.push(chunk);
    currentTokens += estimate;
  }
  if (current.length > 0) batches.push(current);
  return batches;
}
```

### 多 Provider 支持

```typescript
// 支持的嵌入 provider:
// - OpenAI: text-embedding-3-small/large (8192 tokens)
// - Gemini: embedding-002 (768/1536/3072 维度可配)
// - Voyage: voyage-3 等
// - Mistral: mistral-embed
// - Ollama: 本地模型 (CPU 友好)
// - node-llama-cpp: 本地 GGUF 模型

private async embedChunksWithBatch(chunks, entry, source): Promise<number[][]> {
  if (provider.id === "openai" && this.openAi) {
    return this.embedChunksWithOpenAiBatch(chunks, entry, source);
  }
  if (provider.id === "gemini" && this.gemini) {
    return this.embedChunksWithGeminiBatch(chunks, entry, source);
  }
  return this.embedChunksInBatches(chunks);  // 非 batch 降级
}
```

### Batch API 与降级

```typescript
// 优先使用 Batch API（异步、便宜）
// 失败 2 次后自动降级到非 batch

private async runBatchWithFallback<T>(params) {
  try {
    const result = await params.run();
    await this.resetBatchFailureCount();
    return result;
  } catch (err) {
    const { disabled } = await this.recordBatchFailure({
      provider: params.provider,
      message: err.message,
    });
    if (disabled) {
      // 2 次失败后禁用 batch，降级到非 batch
      return await params.fallback();
    }
    throw err;
  }
}
```

### 嵌入缓存（LRU）

```typescript
// 查询缓存
private loadEmbeddingCache(hashes: string[]): Map<string, number[]> {
  // 按 (provider, model, provider_key, hash) 查询
  // 批量查询，每次 400 条（避免 SQL 参数限制）
  const stmt = db.prepare(`
    SELECT hash, embedding FROM embedding_cache
    WHERE provider = ? AND model = ? AND provider_key = ?
      AND hash IN (${placeholders})
  `);
  return new Map(results.map(r => [r.hash, parseEmbedding(r.embedding)]));
}

// 写入缓存
private upsertEmbeddingCache(entries: Array<{ hash: string; embedding: number[] }>) {
  const stmt = db.prepare(`
    INSERT INTO embedding_cache (provider, model, provider_key, hash, embedding, updated_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT (provider, model, provider_key, hash)
    DO UPDATE SET embedding = excluded.embedding, updated_at = excluded.updated_at
  `);
  for (const entry of entries) {
    stmt.run(provider, model, providerKey, entry.hash, JSON.stringify(entry.embedding), Date.now());
  }
}
```

### 重试与指数退避

```typescript
protected async embedBatchWithRetry(texts: string[]): Promise<number[][]> {
  let attempt = 0;
  let delayMs = 500;
  while (true) {
    try {
      return await this.provider.embedBatch(texts);
    } catch (err) {
      if (!this.isRetryableEmbeddingError(err.message) || attempt >= 3) throw err;
      delayMs = Math.min(delayMs * 2, 8000);  // 500 → 1000 → 2000 → 4000 → 8000
      await sleep(delayMs);
      attempt += 1;
    }
  }
}

private isRetryableEmbeddingError(message: string): boolean {
  return /rate[_ ]limit|too many requests|429|resource exhausted|5\d\d/i.test(message);
}
```

---

## MemoryIndexManager：主管理器

源码：`memory/manager.ts:1-858`

### 全局缓存

```typescript
// 每个 (agentId, workspaceDir, settings) 组合一个 manager 实例
const INDEX_CACHE = new Map<string, MemoryIndexManager>();

export async function get(params: {
  agentId: string;
  workspaceDir: string;
  config: OpenClawConfig;
}): Promise<MemoryIndexManager> {
  const key = computeCacheKey(params);
  let manager = INDEX_CACHE.get(key);
  if (!manager) {
    manager = new MemoryIndexManager(params);
    INDEX_CACHE.set(key, manager);
    await manager.initialize();
  }
  return manager;
}
```

### Provider 降级

```typescript
// 嵌入 provider 失败时自动降级
async activateFallbackProvider(reason: string) {
  // OpenAI → Gemini → Voyage → Ollama (本地)
  const fallback = resolveFallbackEmbeddingProvider(this.config);
  if (fallback) {
    this.provider = fallback;
    this.markDirty("memory");   // 需要用新 provider 重新嵌入
    this.markDirty("sessions");
  }
}
```

---

## 数据流总结：一个 memory 文件的生命周期

以用户创建 `memory/project-notes.md` 为例：

```
1. 文件创建 → chokidar 触发 "add" 事件

2. markDirty("memory") → 标记需要同步

3. runSync() 触发:
   ├── listMemoryFiles() → 发现 project-notes.md
   ├── hashText(content) → "abc123..."
   ├── db.getFile("project-notes.md") → null (新文件)
   └── indexFile():

4. chunkMarkdown(content, { tokens: 512, overlap: 64 }):
   ├── 分块 1: lines 1-20, 1800 chars
   ├── 分块 2: lines 18-40, 1900 chars (overlap 2 行)
   └── 分块 3: lines 38-55, 1200 chars

5. 嵌入生成:
   ├── loadEmbeddingCache(["hash1", "hash2", "hash3"])
   │   → 全部未命中
   ├── buildEmbeddingBatches([chunk1, chunk2, chunk3])
   │   → 1 batch (3 chunks < 8000 tokens)
   ├── embedBatchWithRetry(["chunk1 text", "chunk2 text", "chunk3 text"])
   │   → OpenAI API 调用 → [vec1, vec2, vec3]
   └── upsertEmbeddingCache([{hash1, vec1}, {hash2, vec2}, {hash3, vec3}])

6. SQLite 写入:
   ├── INSERT INTO files (path, hash, mtime, size, source)
   ├── INSERT INTO chunks (id, path, text, hash, model, embedding, ...)  × 3
   ├── INSERT INTO chunks_vec (id, embedding)  × 3
   └── FTS5 自动索引 chunks_fts
```

---

## 设计洞察

### SQLite 为什么够用？

OpenClaw 的 memory 是**个人助手级别**——一个用户的记忆文件通常是几十到几百个 .md 文件，总量在 MB 级。SQLite 在这个规模下的性能绰绰有余：
- 向量搜索：sqlite-vec 对几千条向量的余弦距离计算是毫秒级的
- 全文搜索：FTS5 对 MB 级文本的 BM25 检索是微秒级的

如果规模更大，可以切换到 QMD 外部后端。

### 安全重建 vs 就地更新

当嵌入模型变化时，所有旧的嵌入向量都失效了（不同模型的向量空间不兼容）。OpenClaw 选择**安全重建**而不是就地更新：
- 临时数据库 → 构建新索引 → 原子交换
- 迁移旧嵌入缓存（如果新模型和旧模型相同 provider，缓存可能部分复用）
- 失败自动回滚

这确保了搜索服务在重建过程中不中断。

### 嵌入缓存的经济性

嵌入 API 调用是有成本的。缓存策略：
- 按 `(provider, model, hash)` 缓存
- 文件内容不变 → hash 不变 → 缓存命中 → 零 API 调用
- 文件修改 → 只有变化的分块需要重新嵌入
- 切换嵌入模型 → 缓存全部失效，需要重新嵌入

这在实际使用中意味着：日常修改几个文件，只需要几次嵌入 API 调用。
