# Claude Code Permission / Sandbox Deep Dives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing Permission / Sandbox overview into a navigable implementation study comprising four source-backed deep dives that explain permission decisions, Bash command analysis, sandbox runtime containment, and end-to-end behavior.

**Architecture:** Keep `06-permission-and-sandbox.md` as the concise conceptual entry point. Add four mechanism-focused documents under `ai/claude-code-source/deep-dives/`; each follows one control flow, uses short real-source excerpts only where useful, labels pseudocode and inference explicitly, and links to the next layer instead of duplicating it. Treat Claude Code’s adapter and the external Anthropic Sandbox Runtime as separate source layers with separately recorded revisions.

**Tech Stack:** Markdown, Mermaid, TypeScript/TSX source reading, CodeGraph MCP for structural tracing, `rg` for literal checks, Git for isolated documentation commits, and primary-source review of [`anthropic-experimental/sandbox-runtime`](https://github.com/anthropic-experimental/sandbox-runtime).

---

## Source and Evidence Rules

Use these rules throughout execution:

- Claude Code source is read-only at `/Users/buoy/Development/gitrepo/Claude-Code-true`.
- Record its exact revision with:

  ```bash
  git -C /Users/buoy/Development/gitrepo/Claude-Code-true rev-parse HEAD
  ```

  The revision at plan-writing time was `712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf`; use the revision returned at execution time if it differs.

- The Claude Code snapshot imports `@anthropic-ai/sandbox-runtime`, but does not contain that package’s implementation. Use the official public source at `https://github.com/anthropic-experimental/sandbox-runtime` for the OS-level layer.
- Record the exact sandbox-runtime commit or release inspected. Never mix behavior from an unrecorded latest branch into statements about the Claude Code snapshot.
- Use `codegraph_context` first for mechanism questions and at most one focused `codegraph_explore` call per source project when several related bodies are needed.
- Use native text search only for literal settings names, comments, messages, or evidence unavailable through CodeGraph.
- Mark statements as **推論**, **尚未確認**, or **版本限制** when primary source does not establish them.
- Do not modify either source repository.

## File Structure

Create:

- `ai/claude-code-source/deep-dives/06a-permission-decision.md`
  - Responsibility: explain how a validated `tool_use` becomes allow, ask, or deny, including rule priority, tool-specific checks, permission modes, UI/headless behavior, state updates, and abort.
- `ai/claude-code-source/deep-dives/06b-bash-security-analysis.md`
  - Responsibility: explain how Bash commands are parsed, normalized, split, matched against rules, classified as unsafe or ambiguous, and converted into approval suggestions.
- `ai/claude-code-source/deep-dives/06c-sandbox-runtime.md`
  - Responsibility: explain Claude Code’s sandbox adapter and shell execution path, then cross the package boundary into the official sandbox-runtime implementation for macOS/Linux filesystem and network containment.
- `ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md`
  - Responsibility: run the agreed scenario matrix through permission, Bash analysis, sandbox selection, OS containment, process execution, and `tool_result`.

Modify:

- `ai/claude-code-source/06-permission-and-sandbox.md`
  - Responsibility: remain the concise overview, add the simplified complete chain, define layer boundaries, and route readers to the four deep dives.
- `ai/claude-code-source/README.md`
  - Responsibility: expose the new deep-dive layer from the top-level reading guide without changing the existing `00`–`14` sequence.
- `ai/claude-code-source/13-source-code-map.md`
  - Responsibility: add the sandbox-runtime package boundary and the additional shell/sandbox symbols discovered while writing the deep dives.

No application code changes or automated product tests are required. Verification consists of source-evidence checks, required-section checks, internal link checks, scenario coverage, Markdown hygiene, and staged-diff review.

---

### Task 1: Write the Permission Decision Deep Dive

**Files:**
- Create: `ai/claude-code-source/deep-dives/06a-permission-decision.md`

**Primary Claude Code sources:**
- `src/Tool.ts`: `Tool`, `checkPermissions`, `ToolPermissionContext`
- `src/utils/permissions/permissionSetup.ts`: `initializeToolPermissionContext`, mode transitions, dangerous-rule cleanup
- `src/utils/permissions/permissions.ts`: `hasPermissionsToUseTool`, `hasPermissionsToUseToolInner`, `checkRuleBasedPermissions`
- `src/utils/permissions/PermissionResult.ts`
- `src/utils/permissions/PermissionRule.ts`
- `src/utils/permissions/PermissionUpdate.ts`
- `src/utils/permissions/denialTracking.ts`
- `src/hooks/useCanUseTool.tsx`
- `src/cli/print.ts`: headless permission handling
- `src/services/tools/toolHooks.ts`: hook permission decisions

- [ ] **Step 1: Capture the exact permission control flow**

Use `codegraph_context` on `/Users/buoy/Development/gitrepo/Claude-Code-true` with this task:

```text
Trace how a validated tool_use becomes allow, ask, or deny. Cover initializeToolPermissionContext, hasPermissionsToUseTool, hasPermissionsToUseToolInner, checkRuleBasedPermissions, Tool.checkPermissions, permission modes, approval updates, headless behavior, denial tracking, hooks, and abort.
```

Then use one `codegraph_explore` query containing only the surfaced symbols that require full source. Build a private evidence outline in working memory with:

```text
entry
→ early abort
→ whole-tool deny
→ whole-tool ask and sandbox auto-allow exception
→ tool.checkPermissions
→ tool-level deny / ask / safety / passthrough / allow
→ bypass / always-allow / mode-specific paths
→ outer dontAsk or auto transformation
→ denial-state update
→ final PermissionDecision
```

Expected: every arrow is tied to a real symbol; ordering follows source, not the old overview.

- [ ] **Step 2: Create the document with the fixed deep-dive structure**

Create `ai/claude-code-source/deep-dives/06a-permission-decision.md` with these headings:

```markdown
# 06a - Permission Decision：tool_use 如何變成 allow / ask / deny

> Source snapshot

## 這項機制真正解決什麼問題
## 先看完整裁決流程
## 輸入、輸出與關鍵狀態
## 啟動時如何建立 ToolPermissionContext
## tool_use 前的真實裁決順序
## 通用權限層與 Tool.checkPermissions 如何分工
## permission modes 如何改變 ask
## 使用者批准或拒絕後，狀態如何更新
## Hooks、headless 與 subagent 邊界
## Abort 與失敗如何傳播
## 走一遍具體案例
## 證據、限制與設計取捨
## 源碼入口
```

The `Source snapshot` block must contain the exact Claude Code commit and state that this article does not cover OS containment.

- [ ] **Step 3: Add the complete decision pseudocode**

Under `## 先看完整裁決流程`, add explicitly labelled pseudocode. It must preserve the source’s early-return order and visibly separate:

```text
inner permission decision
outer mode transformation
state bookkeeping after the decision
```

Do not collapse `dontAsk` into the inner function if the source applies it afterward. Include the sandbox auto-allow exception to whole-tool ask rules, but link forward to `06c` rather than explaining containment here.

- [ ] **Step 4: Explain every permission mode with a result table**

Add a table with one row each for:

```text
default
plan
acceptEdits
auto
bypassPermissions
dontAsk
```

Columns:

```text
mode | what happens to an unmatched action | what can still block it | whether user UI is expected | important state changes
```

Verify each cell against source. Do not describe bypass as removing all checks.

- [ ] **Step 5: Add short source excerpts and concrete cases**

Include no more than four short excerpts:

1. abort check or decision entry;
2. deny/ask/tool-check ordering;
3. outer `dontAsk` or auto handling;
4. denial tracking or permission update.

Each excerpt must be followed immediately by an explanation of:

```text
what the code reads
what branch it selects
what state or result it produces
why the ordering matters
```

Add at least three complete cases:

- whole-tool deny;
- tool-specific ask followed by user approval;
- ask transformed into deny under `dontAsk`.

- [ ] **Step 6: Validate required coverage**

Run:

```bash
test -f ai/claude-code-source/deep-dives/06a-permission-decision.md
```

Expected: exit status 0.

Run:

```bash
rg -n "ToolPermissionContext|hasPermissionsToUseTool|checkPermissions|default|plan|acceptEdits|auto|bypassPermissions|dontAsk|Abort|headless|推論|源碼入口" ai/claude-code-source/deep-dives/06a-permission-decision.md
```

Expected: every required term is present in a substantive section.

Run:

```bash
rg -n "TODO|TBD|之後再補|待補|自行理解" ai/claude-code-source/deep-dives/06a-permission-decision.md
```

Expected: no output.

- [ ] **Step 7: Commit the permission deep dive**

Run:

```bash
git add ai/claude-code-source/deep-dives/06a-permission-decision.md
git commit -m "docs: explain Claude Code permission decisions"
```

Expected: commit succeeds with only `06a-permission-decision.md`.

---

### Task 2: Write the Bash Security Analysis Deep Dive

**Files:**
- Create: `ai/claude-code-source/deep-dives/06b-bash-security-analysis.md`

**Primary Claude Code sources:**
- `src/tools/BashTool/BashTool.tsx`
- `src/tools/BashTool/bashPermissions.ts`
- `src/tools/BashTool/bashCommandHelpers.ts`
- `src/tools/BashTool/bashSecurity.ts`
- `src/tools/BashTool/shouldUseSandbox.ts`
- `src/utils/bash/ast.ts`
- `src/utils/bash/bashParser.ts`
- `src/utils/bash/commands.ts`
- `src/utils/bash/treeSitterAnalysis.ts`
- `src/utils/permissions/shellRuleMatching.ts`
- `src/utils/permissions/permissionSetup.ts`

- [ ] **Step 1: Trace the Bash command-analysis pipeline**

Use `codegraph_context` with:

```text
Trace BashTool command-level permission analysis from BashTool.checkPermissions through bashToolHasPermission, parseForSecurity, compound-command handling, rule parsing and matching, wrapper and environment stripping, approval suggestions, dangerous-rule cleanup, and shouldUseSandbox excludedCommands matching.
```

Use one focused `codegraph_explore` for the main symbols. Produce this source-backed pipeline:

```text
Bash input
→ schema/value validation
→ shell structure analysis
→ simple / too-complex / unavailable result
→ compound-command decomposition
→ command candidate normalization
→ deny / ask / allow rule matching
→ unsafe-command and safety checks
→ suggestion generation or conservative ask/deny
→ PermissionResult
```

Expected: each transformation identifies the function responsible and the reason it exists.

- [ ] **Step 2: Create the document**

Create `ai/claude-code-source/deep-dives/06b-bash-security-analysis.md` with:

```markdown
# 06b - Bash Security Analysis：runtime 如何理解一條 shell command

> Source snapshot

## 為什麼 Bash 不能只比對原始字串
## 完整分析管線
## BashTool 輸入與 PermissionResult
## shell parser 能確認什麼
## simple、too-complex、parse-unavailable 的分流
## compound command 如何拆分
## exact、prefix、wildcard 規則如何匹配
## env var 與 wrapper stripping
## unsafe command 與保守回退
## approval suggestion 如何避免過度授權
## dangerous permission cleanup
## excludedCommands 為何不是安全邊界
## 走一遍具體案例
## 證據、限制與設計取捨
## 源碼入口
```

- [ ] **Step 3: Add diagrams and normalization examples**

Add one Mermaid flowchart with explicit decision owners:

```text
BashTool
parser
rule matcher
safety checks
permission layer
```

Add a normalization table containing at least:

```text
git status
git status && curl example.com
FOO=bar bazel run //target
timeout 30 bazel test //...
RUN=/tmp/tool python3 script.py
sh -c "..."
malformed shell syntax
```

For each example, show candidate forms, whether stripping stops, which rule style can match, and why.

- [ ] **Step 4: Explain rule parsing and suggestion generation with source excerpts**

Use short excerpts for:

- `bashPermissionRule` or the shared parser contract;
- `stripAllLeadingEnvVars`;
- `getSimpleCommandPrefix` or `getFirstWordPrefix`;
- compound-command or unsafe-command handling.

Explain why safe stripping and approval suggestions use different constraints. Explicitly cover binary-hijack variables and bare shell/wrapper prefixes.

- [ ] **Step 5: Explain excludedCommands without overstating it**

Show the true `shouldUseSandbox` relationship:

```text
permission decides whether execution is authorized
excludedCommands only decides whether an authorized command skips containment
```

Explain:

- compound commands are checked per subcommand;
- env/wrapper stripping reaches a fixed point;
- parse failure falls back to checking the original command;
- bypassing this convenience matcher is not itself a security-boundary failure.

Do not duplicate the OS containment explanation from `06c`.

- [ ] **Step 6: Add at least four complete examples**

Include:

1. simple exact allow;
2. compound command with mixed rule outcomes;
3. wrapper/env-prefixed command;
4. unparseable or too-complex command that follows a conservative path.

Each example must state:

```text
raw input
parser result
normalized candidates
matched or unmatched rules
safety result
final PermissionResult
```

- [ ] **Step 7: Validate and commit**

Run:

```bash
test -f ai/claude-code-source/deep-dives/06b-bash-security-analysis.md
```

Expected: exit status 0.

Run:

```bash
rg -n "parseForSecurity|simple|too-complex|parse-unavailable|exact|prefix|wildcard|stripAllLeadingEnvVars|wrapper|approval suggestion|excludedCommands|安全邊界|源碼入口" ai/claude-code-source/deep-dives/06b-bash-security-analysis.md
```

Expected: every mechanism appears.

Run:

```bash
git add ai/claude-code-source/deep-dives/06b-bash-security-analysis.md
git commit -m "docs: explain Claude Code Bash security analysis"
```

Expected: commit contains only `06b-bash-security-analysis.md`.

---

### Task 3: Write the Sandbox Runtime Deep Dive

**Files:**
- Create: `ai/claude-code-source/deep-dives/06c-sandbox-runtime.md`

**Primary Claude Code sources:**
- `src/utils/sandbox/sandbox-adapter.ts`
- `src/tools/BashTool/shouldUseSandbox.ts`
- `src/utils/Shell.ts`
- `src/tools/BashTool/BashTool.tsx`
- `src/components/sandbox/SandboxConfigTab.tsx`
- `src/components/sandbox/SandboxDependenciesTab.tsx`
- `src/components/sandbox/SandboxDoctorSection.tsx`
- `src/components/sandbox/SandboxSettings.tsx`
- `src/utils/settings/types.ts`

**Primary sandbox-runtime source:**
- `https://github.com/anthropic-experimental/sandbox-runtime`
- `src/sandbox/sandbox-manager.ts`
- `src/sandbox/macos-sandbox-utils.ts`
- `src/sandbox/linux-sandbox-utils.ts`
- `src/sandbox/http-proxy.ts`
- `src/sandbox/socks-proxy.ts`
- `src/sandbox/sandbox-violation-store.ts`
- `src/sandbox/sandbox-schemas.ts`
- `vendor/seccomp-src/`
- `test/sandbox/allow-read.test.ts`
- `test/sandbox/check-dependencies.test.ts`
- `test/sandbox/integration.test.ts`
- `test/sandbox/linux-dependency-error.test.ts`
- `test/sandbox/macos-seatbelt.test.ts`
- `test/sandbox/mandatory-deny-paths.test.ts`
- `test/sandbox/pid-namespace-isolation.test.ts`
- `test/sandbox/proxy-env-vars.test.ts`
- `test/sandbox/request-filter.test.ts`
- `test/sandbox/seccomp-filter.test.ts`
- `test/sandbox/symlink-boundary.test.ts`
- `test/sandbox/update-config.test.ts`
- `test/sandbox/wrap-with-sandbox.test.ts`

- [ ] **Step 1: Pin both source layers**

Record:

```text
Claude Code commit
sandbox-runtime commit or tag
inspection date
```

If the public runtime has changed since the Claude Code snapshot and an exact dependency version cannot be recovered, state this limitation in the article:

```text
Claude Code adapter behavior is tied to the recorded Claude Code commit.
OS-level explanations are tied to the separately recorded public sandbox-runtime commit.
Their API shapes are compared, but exact package-version identity is not asserted without evidence.
```

- [ ] **Step 2: Trace the Claude Code adapter and process path**

Use `codegraph_context` on Claude Code with:

```text
Trace sandboxed Bash execution from permission approval through shouldUseSandbox, Shell.exec, SandboxManager.wrapWithSandbox, spawn, abort, cleanupAfterCommand, and annotateStderrWithSandboxFailures. Include adapter settings conversion, initialization, refresh, required policy, dependency checks, and network initialization.
```

Use one `codegraph_explore` for:

```text
convertToSandboxRuntimeConfig
isSandboxingEnabled
getSandboxUnavailableReason
initialize
refreshConfig
wrapWithSandbox
shouldUseSandbox
Shell.exec
cleanupAfterCommand
```

Expected: a complete Claude Code-side chain, including the exact point where control crosses into `BaseSandboxManager`.

- [ ] **Step 3: Trace the official sandbox-runtime implementation**

Use the official repository’s source graph if available; otherwise inspect its focused files directly. Establish:

```text
SandboxManager.initialize
→ validated runtime config
→ proxy/network setup
→ platform-specific wrapper selection
→ macOS profile generation or Linux bwrap arguments
→ wrapped command string
→ caller spawn
→ violation/cleanup path
```

Also establish the enforcement model:

```text
macOS: sandbox-exec / Seatbelt profile + controlled proxy port
Linux: bubblewrap namespaces/mounts + Unix-socket proxy bridge + optional seccomp socket blocking
```

Do not rely on README claims when source provides a more precise or narrower behavior.

- [ ] **Step 4: Create the document**

Create `ai/claude-code-source/deep-dives/06c-sandbox-runtime.md` with:

```markdown
# 06c - Sandbox Runtime：允許後的 command 如何被限制

> Source snapshots and package boundary

## Permission 與 Sandbox 的最後分界
## 端到端執行鏈
## Claude Code adapter 與 sandbox-runtime 的責任分工
## settings 如何變成 SandboxRuntimeConfig
## sandbox 是否啟用：平台、設定、依賴與 policy
## shouldUseSandbox 的逐項判斷
## 初始化生命週期與競態防護
## 檔案系統限制如何組合
## 網路限制與 proxy 架構
## macOS：Seatbelt profile 如何限制 process tree
## Linux / WSL：bubblewrap、namespace、mount 與 seccomp
## command 如何被 wrap 並交給 Shell.exec spawn
## abort、cleanup 與 cwd/output 處理
## violation 如何回到 stderr 與 tool_result
## 初始化或依賴失敗時如何處理
## 動態設定何時生效
## 走一遍具體案例
## 證據邊界、限制與設計取捨
## 源碼入口
```

- [ ] **Step 5: Add the adapter/runtime boundary diagram**

Add a Mermaid sequence diagram containing:

```text
Permission layer
BashTool
shouldUseSandbox
Shell.exec
Claude Code SandboxManager adapter
BaseSandboxManager
macOS or Linux wrapper
child process
violation store / result mapping
```

The diagram must show:

- authorization completes before containment;
- initialization is awaited before wrapping;
- `wrapWithSandbox` returns a command string;
- `Shell.exec` owns the actual `spawn`;
- cleanup and violation annotation occur after or around process completion.

- [ ] **Step 6: Explain configuration conversion with concrete tables**

Add tables for:

1. Claude Code settings → runtime config fields;
2. filesystem precedence;
3. network precedence;
4. required vs optional sandbox failure behavior;
5. platform dependency differences.

Filesystem table must distinguish:

```text
read: deny regions with re-allow inside them
write: allow-only with deny taking precedence inside allowed paths
```

Network table must distinguish:

```text
allowed hosts
denied hosts
managed-only policy
dynamic ask callback
HTTP proxy
SOCKS proxy
Unix sockets
local binding
```

- [ ] **Step 7: Explain initialization, refresh, and failure semantics**

Use short real-source excerpts for:

- synchronous assignment of `initializationPromise`;
- `wrapWithSandbox` waiting for initialization;
- settings subscription or synchronous `refreshConfig`;
- initialization catch/reset behavior;
- `isSandboxRequired` or unavailable-reason handling.

For each failure branch, answer:

```text
does execution continue unsandboxed?
does permission still apply?
is retry possible?
what user-visible diagnostic exists?
does policy prohibit fallback?
```

Do not infer fail-open or fail-closed behavior from a catch block alone; trace its caller.

- [ ] **Step 8: Explain platform enforcement from source**

For macOS, cover:

- dynamic Seatbelt profile generation;
- process-tree enforcement;
- read/write path rules;
- network channel restricted to the proxy;
- violation log monitoring;
- Unix socket and optional Apple Events/weaker-network caveats if present in the pinned source.

For Linux/WSL, cover:

- bubblewrap mount and namespace construction;
- network namespace removal;
- proxy access through mounted Unix sockets and `socat` where applicable;
- seccomp’s role in blocking Unix sockets and architecture/dependency limitations;
- literal-path limitation versus macOS glob support;
- cleanup of host-side mount-point artifacts described by Claude Code’s `Shell.exec`.

Every platform claim must cite either a short source excerpt, a symbol, or a test.

- [ ] **Step 9: Add complete sandbox cases**

Include at least:

1. allowed workspace write;
2. denied write outside allowed paths;
3. allowed host through proxy;
4. denied or unknown host;
5. `dangerouslyDisableSandbox` allowed and disallowed;
6. dependency missing under optional and required policy;
7. abort during a sandboxed process;
8. settings change followed by the next command.

Each case must identify which behavior is implemented by Claude Code and which by sandbox-runtime.

- [ ] **Step 10: Validate and commit**

Run:

```bash
test -f ai/claude-code-source/deep-dives/06c-sandbox-runtime.md
```

Expected: exit status 0.

Run:

```bash
rg -n "Source snapshots|SandboxRuntimeConfig|shouldUseSandbox|initializationPromise|refreshConfig|Seatbelt|sandbox-exec|bubblewrap|bwrap|seccomp|HTTP proxy|SOCKS|Unix socket|wrapWithSandbox|Shell.exec|spawn|Abort|violation|required|版本限制|源碼入口" ai/claude-code-source/deep-dives/06c-sandbox-runtime.md
```

Expected: all critical layers are covered.

Run:

```bash
rg -n "TODO|TBD|之後再補|底層應該|大概是|自行理解" ai/claude-code-source/deep-dives/06c-sandbox-runtime.md
```

Expected: no output.

Run:

```bash
git add ai/claude-code-source/deep-dives/06c-sandbox-runtime.md
git commit -m "docs: explain Claude Code sandbox runtime"
```

Expected: commit contains only `06c-sandbox-runtime.md`.

---

### Task 4: Write the End-to-End Scenario Deep Dive

**Files:**
- Create: `ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md`

- [ ] **Step 1: Build the scenario result matrix from the first three articles**

Create a private matrix with these columns:

```text
scenario
initial settings and policy
permission decision
Bash parser/rule result
shouldUseSandbox result
adapter/runtime action
OS/process result
tool_result
evidence
```

Populate all fourteen scenarios from the approved design before writing prose. If a result is uncertain, return to source; do not resolve it by intuition.

- [ ] **Step 2: Create the document**

Create `ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md` with:

```markdown
# 06d - End-to-End Scenarios：從 tool_use 到 tool_result

> Source snapshots

## 如何閱讀案例
## 共用執行管線
## Scenario 1：權限批准並在 sandbox 中完成
## Scenario 2：whole-tool deny，未進入 Bash 分析與 sandbox
## Scenario 3：內容級 ask 後被使用者拒絕
## Scenario 4：工作區可讀寫，但外部寫入被 OS 阻擋
## Scenario 5：已允許 host 經 proxy 存取
## Scenario 6：未知 host 經 ask callback 批准
## Scenario 7：managed-only policy 阻止動態 host 批准
## Scenario 8：compound command 命中 excludedCommands
## Scenario 9：dangerouslyDisableSandbox 被 policy 允許
## Scenario 10：dangerouslyDisableSandbox 不被 policy 允許
## Scenario 11：sandbox 不可用且非 required
## Scenario 12：sandbox 不可用且 required
## Scenario 13：執行中的 command 被 abort
## Scenario 14：settings 更新後的下一條 command
## 跨案例比較
## 哪些結果仍受版本或環境影響
## 源碼入口
```

- [ ] **Step 3: Use the same trace template for every scenario**

Every scenario must include:

```markdown
### 輸入
### 初始狀態
### 逐層執行
### 最終結果
### 為什麼
### 證據
```

`逐層執行` must explicitly list:

```text
permission
Bash analysis
sandbox decision
runtime/OS
tool_result
```

When a layer is not reached, write `未進入此層` and explain which earlier decision stopped it.

- [ ] **Step 4: Add a cross-scenario ownership table**

The final comparison table must answer:

```text
who authorized?
who interpreted the command?
who selected containment?
who enforced the restriction?
who converted the outcome to tool_result?
```

This table is the integration check that permission and sandbox responsibilities have not been conflated.

- [ ] **Step 5: Validate all scenarios and commit**

Run:

```bash
rg -c "^## Scenario" ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md
```

Expected: `14`.

Run:

```bash
rg -c "^### 輸入|^### 初始狀態|^### 逐層執行|^### 最終結果|^### 為什麼|^### 證據" ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md
```

Expected: `84` total matching subsection headings.

Run:

```bash
rg -n "未進入此層|permission|Bash analysis|sandbox decision|runtime/OS|tool_result|版本限制" ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md
```

Expected: all trace layers and explicit stop behavior appear.

Run:

```bash
git add ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md
git commit -m "docs: add Permission Sandbox end-to-end scenarios"
```

Expected: commit contains only `06d-end-to-end-scenarios.md`.

---

### Task 5: Convert Chapter 06 into the Overview and Navigation Layer

**Files:**
- Modify: `ai/claude-code-source/06-permission-and-sandbox.md`

- [ ] **Step 1: Preserve the useful concise material**

Keep:

- the interview-style answer;
- the three-layer mental model;
- the compact full-chain Mermaid diagram;
- core design trade-offs;
- interview follow-ups;
- one-sentence summary.

Remove or compress duplicated implementation detail that now belongs exclusively to `06a`–`06c`.

- [ ] **Step 2: Add the deep-dive navigation**

Add a section near the beginning:

```markdown
## Implementation Deep Dives

| 問題 | 閱讀 |
| --- | --- |
| tool_use 為什麼被 allow / ask / deny？ | [06a - Permission Decision](./deep-dives/06a-permission-decision.md) |
| Bash command 如何被解析與匹配規則？ | [06b - Bash Security Analysis](./deep-dives/06b-bash-security-analysis.md) |
| sandbox 如何限制檔案、網路與 process？ | [06c - Sandbox Runtime](./deep-dives/06c-sandbox-runtime.md) |
| 一個具體輸入最後會得到什麼結果？ | [06d - End-to-End Scenarios](./deep-dives/06d-end-to-end-scenarios.md) |
```

- [ ] **Step 3: Add one simplified complete chain**

The overview chain must fit in one screen and show only:

```text
model tool_use
→ schema validation and hooks
→ permission decision
→ Bash command analysis
→ shouldUseSandbox
→ sandbox wrapper or direct shell
→ process execution
→ tool_result
```

Link each stage to the article that owns its detail.

- [ ] **Step 4: Verify the overview does not duplicate deep implementation**

Run:

```bash
rg -n "stripAllLeadingEnvVars|initializationPromise|bubblewrap mount|Seatbelt profile generation|seccomp BPF" ai/claude-code-source/06-permission-and-sandbox.md
```

Expected: either no output or only brief navigation references, not full explanations.

- [ ] **Step 5: Verify links and commit**

Run:

```bash
test -f ai/claude-code-source/deep-dives/06a-permission-decision.md
test -f ai/claude-code-source/deep-dives/06b-bash-security-analysis.md
test -f ai/claude-code-source/deep-dives/06c-sandbox-runtime.md
test -f ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md
```

Expected: all commands exit with status 0.

Run:

```bash
git add ai/claude-code-source/06-permission-and-sandbox.md
git commit -m "docs: turn Permission Sandbox chapter into overview"
```

Expected: commit contains only the overview.

---

### Task 6: Update Top-Level Navigation and Source Map

**Files:**
- Modify: `ai/claude-code-source/README.md`
- Modify: `ai/claude-code-source/13-source-code-map.md`

- [ ] **Step 1: Add the deep-dive layer to README**

After the `06 - Permission 与 Sandbox` navigation entry, add an indented list linking all four deep dives. In `怎么使用这组笔记`, explain:

```text
00–14 establish the runtime model.
deep-dives reconstruct implementation mechanisms.
Start with the overview; enter a deep dive only when following a concrete control flow.
```

- [ ] **Step 2: Expand the source map**

Under `Permission / Sandbox`, include the additional verified entries:

```text
src/utils/Shell.ts / exec
src/utils/sandbox/sandbox-adapter.ts / convertToSandboxRuntimeConfig
src/utils/sandbox/sandbox-adapter.ts / initialize
src/utils/sandbox/sandbox-adapter.ts / wrapWithSandbox
src/tools/BashTool/shouldUseSandbox.ts / containsExcludedCommand
src/components/sandbox/SandboxDependenciesTab.tsx
external: anthropic-experimental/sandbox-runtime
```

Add a clear package-boundary note: Claude Code owns configuration and integration; sandbox-runtime owns the platform-specific wrapper and enforcement implementation.

- [ ] **Step 3: Validate navigation**

Run:

```bash
rg -n "06a-permission-decision|06b-bash-security-analysis|06c-sandbox-runtime|06d-end-to-end-scenarios" ai/claude-code-source/README.md ai/claude-code-source/06-permission-and-sandbox.md
```

Expected: all four links appear in both navigation surfaces.

Run:

```bash
rg -n "src/utils/Shell.ts|convertToSandboxRuntimeConfig|containsExcludedCommand|anthropic-experimental/sandbox-runtime" ai/claude-code-source/13-source-code-map.md
```

Expected: all source boundaries appear.

- [ ] **Step 4: Commit navigation and source-map updates**

Run:

```bash
git add ai/claude-code-source/README.md ai/claude-code-source/13-source-code-map.md
git commit -m "docs: index Permission Sandbox deep dives"
```

Expected: commit includes only the two navigation files.

---

### Task 7: Run the Cross-Document Evidence and Consistency Audit

**Files:**
- Modify if needed:
  - `ai/claude-code-source/06-permission-and-sandbox.md`
  - `ai/claude-code-source/deep-dives/06a-permission-decision.md`
  - `ai/claude-code-source/deep-dives/06b-bash-security-analysis.md`
  - `ai/claude-code-source/deep-dives/06c-sandbox-runtime.md`
  - `ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md`
  - `ai/claude-code-source/README.md`
  - `ai/claude-code-source/13-source-code-map.md`

- [ ] **Step 1: Check terminology ownership**

Search:

```bash
rg -n "安全邊界|便利功能|authorization|containment|allow|ask|deny|excludedCommands|dangerouslyDisableSandbox" ai/claude-code-source/06-permission-and-sandbox.md ai/claude-code-source/deep-dives
```

Review every occurrence against these invariants:

```text
permission authorizes
Bash analysis interprets command content
shouldUseSandbox selects containment
sandbox-runtime enforces OS restrictions
excludedCommands is convenience, not authorization
tool_result reports execution outcome
```

Fix any sentence that assigns a decision to the wrong layer.

- [ ] **Step 2: Check source and pseudocode labelling**

Run:

```bash
rg -n "```(typescript|tsx|text|mermaid)|偽代碼|原始碼|刪節|推論|尚未確認|版本限制" ai/claude-code-source/deep-dives
```

Expected:

- every compressed cross-file flow is labelled `偽代碼`;
- every edited excerpt is labelled as abridged;
- inferred behavior carries an uncertainty marker;
- Mermaid blocks contain diagrams rather than pseudo-source.

- [ ] **Step 3: Check source snapshot consistency**

Run:

```bash
rg -n "Source snapshot|Source snapshots|Claude Code commit|sandbox-runtime" ai/claude-code-source/deep-dives
```

Expected:

- all four documents identify the Claude Code source revision;
- `06c` and `06d` identify the sandbox-runtime revision;
- no article silently claims the two revisions are an exact dependency match without evidence.

- [ ] **Step 4: Check required concepts and scenario counts**

Run:

```bash
rg -c "^## Scenario" ai/claude-code-source/deep-dives/06d-end-to-end-scenarios.md
```

Expected: `14`.

Run:

```bash
rg -n "whole-tool deny|tool-specific|dontAsk|compound command|parse-unavailable|approval suggestion|initializationPromise|Seatbelt|bubblewrap|seccomp|proxy|Abort|refreshConfig" ai/claude-code-source/deep-dives
```

Expected: every concept is explained in its owning article.

- [ ] **Step 5: Run Markdown and diff hygiene checks**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

Run:

```bash
rg -n "TODO|TBD|之後再補|待補|自行理解|底層應該|大概是" ai/claude-code-source/06-permission-and-sandbox.md ai/claude-code-source/deep-dives ai/claude-code-source/README.md ai/claude-code-source/13-source-code-map.md
```

Expected: no output, except intentional prose explicitly rejecting those phrases; rewrite such prose if it creates false positives.

Run:

```bash
git status --short
```

Expected: only intentional audit corrections are modified; unrelated user changes remain untouched and unstaged.

- [ ] **Step 6: Commit audit fixes**

If audit fixes were required:

```bash
git add ai/claude-code-source/06-permission-and-sandbox.md ai/claude-code-source/deep-dives ai/claude-code-source/README.md ai/claude-code-source/13-source-code-map.md
git commit -m "docs: audit Permission Sandbox deep dives"
```

Expected: commit contains only files in the Permission / Sandbox documentation set.

If no fixes were required, skip the commit and record that the audit passed without changes.

---

### Task 8: Final Reader-Facing Verification

**Files:**
- Read-only verification of all files from Tasks 1–7

- [ ] **Step 1: Answer the six acceptance questions using only the new documents**

Without opening source, write short scratch answers to:

1. Why did a command become allow, ask, or deny?
2. Which layer decided whether it entered the sandbox?
3. How are filesystem and network capabilities restricted after entry?
4. What happens if initialization or dependencies fail under optional and required policy?
5. When does a settings update affect execution?
6. How does abort travel from tool execution to the child process?

Expected: each answer names decisions, state changes, and next components—not merely file or class names.

- [ ] **Step 2: Verify each answer against primary source**

Use CodeGraph or the pinned sandbox-runtime source to check each scratch answer. Correct the documentation if any answer:

- reverses precedence;
- skips a failure branch;
- attributes a decision to the wrong layer;
- claims an exact version relationship without evidence;
- describes a platform capability more broadly than the pinned source.

- [ ] **Step 3: Verify the final staged scope**

Run:

```bash
git status --short
```

Expected: no uncommitted changes in the Permission / Sandbox documentation set.

Run:

```bash
git log --oneline -8 -- ai/claude-code-source
```

Expected: the implementation commits for `06a`, `06b`, `06c`, `06d`, overview, navigation, and any audit fix are visible.

- [ ] **Step 4: Report completion**

Report:

- files created and modified;
- Claude Code and sandbox-runtime revisions used;
- scenario count;
- verification commands run;
- any remaining statements marked **推論**, **尚未確認**, or **版本限制**.

Do not claim the deep dives are complete unless all fourteen scenarios and both source layers have been audited.
