# 07 - Session 管理：JSONL 读写与对话链重建

> Session 系统是 SDK 的"历史档案馆"。
> Claude Code CLI 在 `~/.claude/projects/` 下以 JSONL 文件存储每次会话。
> SDK 提供了读取、列表、重命名、标记等操作。
> 本文分析 Session 的存储格式、查找机制、对话链重建算法、和变更操作。

---

## 存储结构

```
~/.claude/
  └── projects/
      └── <sanitized-project-path>/          ← 每个项目目录一个文件夹
          ├── 550e8400-e29b-41d4-a716-446655440000.jsonl   ← 会话文件
          ├── a1b2c3d4-e5f6-7890-abcd-ef1234567890.jsonl
          └── ...
```

### 路径清理（_sanitize_path）

源码：`_internal/sessions.py:97-107`

```python
_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9]")

def _sanitize_path(name: str) -> str:
    sanitized = _SANITIZE_RE.sub("-", name)  # 非字母数字 → 连字符
    if len(sanitized) <= MAX_SANITIZED_LENGTH:  # 200
        return sanitized
    # 超长路径：截断 + hash 后缀
    h = _simple_hash(name)
    return f"{sanitized[:MAX_SANITIZED_LENGTH]}-{h}"
```

**示例**：
```
/Users/buoy/Development/project
→ -Users-buoy-Development-project

/very/long/path/that/exceeds/200/characters/...
→ -very-long-path-that-exceeds-...(截断到 200)-abc123
```

### _simple_hash — 与 JS 兼容的哈希

```python
def _simple_hash(s: str) -> str:
    h = 0
    for ch in s:
        char = ord(ch)
        h = (h << 5) - h + char
        h = h & 0xFFFFFFFF      # JS 的 |= 0（32 位有符号整数）
        if h >= 0x80000000:
            h -= 0x100000000
    h = abs(h)
    # base36 编码
    ...
```

> **为什么要兼容 JS？** 因为 CLI 是 Node.js 写的，用同样的算法生成目录名。
> SDK 需要用相同算法才能找到 CLI 创建的会话文件。
>
> **Bun vs Node 问题**：CLI 可能在 Bun 或 Node 下运行，两者的哈希实现不同。
> `_find_project_dir()` 会先尝试精确匹配，失败后做前缀匹配来兼容。

---

## 轻量读取 — _read_session_lite()

源码：`_internal/sessions.py:336-363`

```python
LITE_READ_BUF_SIZE = 65536  # 64KB

class _LiteSessionFile:
    __slots__ = ("mtime", "size", "head", "tail")

def _read_session_lite(file_path: Path) -> _LiteSessionFile | None:
    with file_path.open("rb") as f:
        stat = os.fstat(f.fileno())
        size = stat.st_size
        mtime = int(stat.st_mtime * 1000)

        # 读取 head（前 64KB）
        head_bytes = f.read(LITE_READ_BUF_SIZE)
        head = head_bytes.decode("utf-8", errors="replace")

        # 读取 tail（后 64KB）
        tail_offset = max(0, size - LITE_READ_BUF_SIZE)
        if tail_offset == 0:
            tail = head  # 文件小于 64KB，head == tail
        else:
            f.seek(tail_offset)
            tail_bytes = f.read(LITE_READ_BUF_SIZE)
            tail = tail_bytes.decode("utf-8", errors="replace")

        return _LiteSessionFile(mtime=mtime, size=size, head=head, tail=tail)
```

> **为什么只读 head + tail？** 会话文件可能很大（数 MB）。
> 元数据（标题、标签、分支）通常在文件头部或尾部。
> 用 64KB 的 head + tail 就够提取所有需要的信息，避免全量解析。

---

## 元数据提取 — 正则而非 JSON 解析

### _extract_json_string_field — 不解析 JSON 直接提取字段

源码：`_internal/sessions.py:188-209`

```python
def _extract_json_string_field(text: str, key: str) -> str | None:
    patterns = [f'"{key}":"', f'"{key}": "']
    for pattern in patterns:
        idx = text.find(pattern)
        if idx < 0:
            continue
        value_start = idx + len(pattern)
        i = value_start
        while i < len(text):
            if text[i] == "\\":
                i += 2       # 跳过转义
                continue
            if text[i] == '"':
                return _unescape_json_string(text[value_start:i])
            i += 1
    return None
```

**为什么不用 json.loads？**
1. head/tail 可能在 JSON 中间截断 → `json.loads` 会失败
2. JSONL 文件每行一个 JSON → 不能把整个 head 当一个 JSON 解析
3. 字符串搜索 + 手动提取比逐行 `json.loads` 快很多

### _extract_first_prompt_from_head — 提取第一条有效 prompt

源码：`_internal/sessions.py:242-316`

```python
def _extract_first_prompt_from_head(head: str) -> str:
    # 逐行扫描 JSONL
    while start < head_len:
        line = ...

        # 跳过非 user 消息
        if '"type":"user"' not in line:
            continue
        # 跳过 tool_result
        if '"tool_result"' in line:
            continue
        # 跳过 meta 和 compact summary
        if '"isMeta":true' in line:
            continue

        entry = json.loads(line)  # 只在匹配后才解析

        # 提取 content 中的文本
        for raw in texts:
            result = raw.replace("\n", " ").strip()
            # 跳过自动生成的消息（session-start-hook、ide_opened_file 等）
            if _SKIP_FIRST_PROMPT_PATTERN.match(result):
                continue
            # 跳过斜杠命令，但记录为 fallback
            cmd_match = _COMMAND_NAME_RE.search(result)
            if cmd_match:
                command_fallback = cmd_match.group(1)
                continue
            # 截断到 200 字符
            if len(result) > 200:
                result = result[:200].rstrip() + "…"
            return result

    return command_fallback or ""
```

> **跳过模式**：
> - `<local-command-stdout>` — 本地命令输出
> - `<session-start-hook>` — 会话启动 hook
> - `<tick>` — 心跳
> - `<goal>` — 目标设定
> - `[Request interrupted by user...]` — 中断通知
> - `<ide_opened_file>` / `<ide_selection>` — IDE 上下文
>
> 这些都不是用户"真正的"第一条 prompt。

---

## Session 信息解析

### _parse_session_info_from_lite()

源码：`_internal/sessions.py:404-490`

```python
def _parse_session_info_from_lite(session_id, lite, project_path=None):
    head, tail = lite.head, lite.tail

    # 1. 跳过 sidechain 会话
    first_line = head[:head.find("\n")]
    if '"isSidechain":true' in first_line:
        return None

    # 2. 提取标题（优先级：customTitle > aiTitle）
    custom_title = (
        _extract_last_json_string_field(tail, "customTitle")
        or _extract_last_json_string_field(head, "customTitle")
        or _extract_last_json_string_field(tail, "aiTitle")
        or _extract_last_json_string_field(head, "aiTitle")
    )

    # 3. 提取第一条 prompt
    first_prompt = _extract_first_prompt_from_head(head)

    # 4. 生成 summary（优先级：title > lastPrompt > summary > first_prompt）
    summary = (
        custom_title
        or _extract_last_json_string_field(tail, "lastPrompt")
        or _extract_last_json_string_field(tail, "summary")
        or first_prompt
    )

    # 5. 提取其他字段
    git_branch = _extract_last_json_string_field(tail, "gitBranch") or ...
    session_cwd = _extract_json_string_field(head, "cwd") or project_path
    tag = ...  # 只从 {"type":"tag"} 行提取，避免误匹配

    # 6. 提取创建时间
    first_timestamp = _extract_json_string_field(first_line, "timestamp")
    created_at = int(datetime.fromisoformat(first_timestamp).timestamp() * 1000)

    return SDKSessionInfo(
        session_id=session_id,
        summary=summary,
        last_modified=lite.mtime,
        file_size=lite.size,
        custom_title=custom_title,
        first_prompt=first_prompt,
        git_branch=git_branch,
        cwd=session_cwd,
        tag=tag,
        created_at=created_at,
    )
```

> **tag 提取的精确性**：不能直接搜索 `"tag":` 因为工具输入（git tag 命令、Docker tag 等）
> 也可能包含这个字段。所以先找 `{"type":"tag"` 开头的行，再从该行提取 tag 值。

---

## 对话链重建 — parentUuid 图遍历

### get_session_messages() — 入口

源码：`_internal/sessions.py:1012-1068`

```python
def get_session_messages(session_id, directory=None, limit=None, offset=0):
    content = _read_session_file(session_id, directory)  # 读取完整 JSONL

    entries = _parse_transcript_entries(content)   # 解析为 entry 列表
    chain = _build_conversation_chain(entries)     # 重建对话链
    visible = [e for e in chain if _is_visible_message(e)]  # 过滤可见消息
    messages = [_to_session_message(e) for e in visible]    # 转为 SessionMessage

    # 分页
    if limit is not None:
        return messages[offset:offset+limit]
    return messages[offset:]
```

### _parse_transcript_entries() — 提取有效条目

```python
_TRANSCRIPT_ENTRY_TYPES = frozenset({"user", "assistant", "progress", "system", "attachment"})

def _parse_transcript_entries(content):
    entries = []
    for line in content.split("\n"):
        entry = json.loads(line)
        if entry.get("type") in _TRANSCRIPT_ENTRY_TYPES and isinstance(entry.get("uuid"), str):
            entries.append(entry)
    return entries
```

### _build_conversation_chain() — 核心算法

源码：`_internal/sessions.py:889-978`

```python
def _build_conversation_chain(entries):
    # 1. 构建 uuid → entry 索引
    by_uuid = {entry["uuid"]: entry for entry in entries}
    entry_index = {entry["uuid"]: i for i, entry in enumerate(entries)}

    # 2. 找出所有叶子节点（没有子节点指向的条目）
    parent_uuids = {e.get("parentUuid") for e in entries if e.get("parentUuid")}
    terminals = [e for e in entries if e["uuid"] not in parent_uuids]

    # 3. 从每个 terminal 向上走，找到最近的 user/assistant 叶子
    leaves = []
    for terminal in terminals:
        walk_cur = terminal
        while walk_cur is not None:
            if walk_cur.get("type") in ("user", "assistant"):
                leaves.append(walk_cur)
                break
            parent = walk_cur.get("parentUuid")
            walk_cur = by_uuid.get(parent) if parent else None

    # 4. 选择主链叶子（排除 sidechain/team/meta）
    main_leaves = [
        leaf for leaf in leaves
        if not leaf.get("isSidechain")
        and not leaf.get("teamName")
        and not leaf.get("isMeta")
    ]
    leaf = _pick_best(main_leaves) if main_leaves else _pick_best(leaves)

    # 5. 从叶子沿 parentUuid 回溯到根
    chain = []
    chain_cur = leaf
    while chain_cur is not None:
        chain.append(chain_cur)
        parent = chain_cur.get("parentUuid")
        chain_cur = by_uuid.get(parent) if parent else None

    chain.reverse()  # 根 → 叶
    return chain
```

**算法图示**：

```
JSONL 文件中的条目（带 parentUuid 链接）：

entry_1 (user, uuid=A)
  ↓ parentUuid
entry_2 (assistant, uuid=B, parentUuid=A)
  ↓ parentUuid
entry_3 (user, uuid=C, parentUuid=B)
  ↓ parentUuid                    ↘ parentUuid（分支）
entry_4 (assistant, uuid=D)      entry_5 (assistant, uuid=E, sidechain)
  ↓ parentUuid
entry_6 (user, uuid=F, parentUuid=D)
  ↓ parentUuid
entry_7 (assistant, uuid=G, parentUuid=F)  ← terminal（无子节点）

步骤：
1. terminals = [entry_7, entry_5]
2. 从 entry_7 向上走 → 是 assistant → 叶子
   从 entry_5 向上走 → 是 assistant → 叶子
3. main_leaves = [entry_7]（entry_5 是 sidechain）
4. 从 entry_7 回溯：G → F → D → C → B → A
5. 反转：A → B → C → D → F → G
```

> **为什么不跟随 logicalParentUuid？** 因为压缩（compaction）后的 `isCompactSummary` 消息
> 替代了早期消息。跟随 `logicalParentUuid` 会导致内容重复。
> 这与 VS Code IDE 的行为一致。

### _is_visible_message() — 过滤

```python
def _is_visible_message(entry):
    if entry.get("type") not in ("user", "assistant"):
        return False
    if entry.get("isMeta"):
        return False
    if entry.get("isSidechain"):
        return False
    return not entry.get("teamName")
    # 注意：isCompactSummary 消息保留！
```

---

## Session 变更 — rename_session / tag_session

### rename_session()

源码：`_internal/session_mutations.py:42-94`

```python
def rename_session(session_id, title, directory=None):
    if not _validate_uuid(session_id):
        raise ValueError(f"Invalid session_id: {session_id}")
    stripped = title.strip()
    if not stripped:
        raise ValueError("title must be non-empty")

    data = json.dumps({
        "type": "custom-title",
        "customTitle": stripped,
        "sessionId": session_id,
    }, separators=(",", ":")) + "\n"

    _append_to_session(session_id, data, directory)
```

### tag_session()

```python
def tag_session(session_id, tag, directory=None):
    if tag is not None:
        sanitized = _sanitize_unicode(tag).strip()
        if not sanitized:
            raise ValueError("tag must be non-empty (use None to clear)")
        tag = sanitized

    data = json.dumps({
        "type": "tag",
        "tag": tag if tag is not None else "",
        "sessionId": session_id,
    }, separators=(",", ":")) + "\n"

    _append_to_session(session_id, data, directory)
```

### _append_to_session — 原子追加

```python
def _try_append(path: Path, data: str) -> bool:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND)  # 注意：没有 O_CREAT
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ENOTDIR):
            return False  # 文件不存在，继续搜索
        raise

    try:
        stat = os.fstat(fd)
        if stat.st_size == 0:
            return False  # 空文件是"此处无会话"信号
        os.write(fd, data.encode("utf-8"))
        return True
    finally:
        os.close(fd)
```

> **O_APPEND 的原子性**：POSIX 系统上 `O_APPEND` 让每次 write 自动定位到文件末尾，
> 这是原子的（内核保证）。所以即使 CLI 同时在写这个文件，SDK 的追加也不会损坏数据。
>
> **没有 O_CREAT**：只能追加到已有文件。如果文件不存在，open 失败返回 ENOENT，
> SDK 继续搜索其他候选路径。这避免了在错误位置创建新文件。
>
> **空文件检查**：0 字节的 `.jsonl` 文件是一个"此处无会话"信号。
> 不追加到空文件，继续搜索。

### Unicode 清理

```python
_UNICODE_STRIP_RE = re.compile(
    "["
    "\u200b-\u200f"    # 零宽空格、方向标记
    "\u202a-\u202e"    # 方向格式化字符
    "\u2066-\u2069"    # 方向隔离
    "\ufeff"           # BOM
    "\ue000-\uf8ff"    # 私用区
    "]"
)

def _sanitize_unicode(value: str) -> str:
    current = value
    for _ in range(10):      # 最多 10 轮
        previous = current
        current = unicodedata.normalize("NFKC", current)
        # 移除 Cf（格式）、Co（私用）、Cn（未分配）
        current = "".join(c for c in current if unicodedata.category(c) not in {"Cf", "Co", "Cn"})
        current = _UNICODE_STRIP_RE.sub("", current)
        if current == previous:
            break
    return current
```

> **迭代清理**：NFKC 标准化可能产生新的 Cf 字符，所以要迭代直到稳定。
> 最多 10 轮防止无限循环。

---

## Git Worktree 支持

源码：`_internal/sessions.py:371-396`

```python
def _get_worktree_paths(cwd: str) -> list[str]:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=cwd, capture_output=True, text=True, timeout=5,
    )
    paths = []
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            paths.append(unicodedata.normalize("NFC", line[len("worktree "):]))
    return paths
```

> **Worktree 的意义**：同一个 Git 仓库可以有多个 worktree（工作树），
> 每个 worktree 是独立目录，CLI 会为每个 worktree 创建独立的 session 文件夹。
> `list_sessions` 需要扫描所有 worktree 的 session 文件夹才能列出完整的会话历史。

---

## 设计洞察

### 1. JSONL 作为存储格式

JSONL（每行一个 JSON）的优势：
- **追加友好**：新数据直接追加到文件末尾，不需要修改已有内容
- **并发安全**：`O_APPEND` 保证原子追加
- **容错**：某行损坏不影响其他行
- **增量读取**：可以只读 head/tail，不需要全量解析

### 2. head + tail 轻量读取

64KB 的 head + tail 足以提取：
- 标题（customTitle/aiTitle）—— 通常在尾部
- 第一条 prompt —— 在头部
- Git 分支 —— 在尾部
- 标签 —— 在尾部
- 创建时间 —— 第一行的 timestamp

避免了对可能数 MB 的 JSONL 全量解析。

### 3. parentUuid 链式结构

对话不是简单的线性数组，而是一个**有向图**（树结构）：
- 压缩（compaction）会产生分支
- 子 Agent 的 sidechain 是独立分支
- 用户中断和重试也产生分支

`_build_conversation_chain` 通过找叶子 → 回溯到根，重建主干对话链。

### 4. 与 OpenAI Session 的对比

| 维度 | OpenAI Session | Claude Session |
|------|---------------|---------------|
| 存储位置 | SDK 内存 / 用户自定义 | 磁盘 JSONL 文件 |
| 格式 | Python 对象 | JSONL |
| 读取 | 直接访问内存 | 文件 I/O + 解析 |
| 对话结构 | 线性数组 | parentUuid 图 |
| 写入 | SDK 内 `save_result_to_session()` | CLI 自动写 + SDK 追加 |
| 主要维护者 | SDK | CLI（SDK 只做辅助读写） |
