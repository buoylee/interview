# 06b - Bash Security Analysis：runtime 如何理解一條 shell command

> Source snapshot
>
> 本文依據 Claude Code source commit `712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf` 重建。範圍只涵蓋 Bash input 如何被驗證、解析、拆分、正規化、套用 command-level rule 與 safety check，最後產生 `PermissionResult`。通用 permission precedence、mode、hook、互動批准與最終 `PermissionDecision` 屬於 [06a - Permission Decision](./06a-permission-decision.md)；實際 OS containment、檔案系統與網路隔離屬於後續 06c。

## 為什麼 Bash 不能只比對原始字串

同一個可執行動作可以有許多表面形式：

```text
git status
NO_COLOR=1 git status
timeout 30 git status
git status > /tmp/status
git status && curl example.com
```

反過來，表面上以相同字首開頭的字串，也可能在 shell 中執行完全不同的事情：

```text
echo safe && curl example.com
sh -c "arbitrary shell program"
PATH=/tmp/attacker-bin git status
```

因此 runtime 不能把 `startsWith("git ")` 當成授權判斷。它必須先回答三個較窄的問題：

1. 這段文字能否被可靠地解釋成一組 `argv[]`、environment assignment 與 redirect？
2. compound command 中實際有幾個 leaf command，每個 leaf 各自匹配什麼 rule？
3. 正規化是否會隱藏會改變 binary、module、工作目錄或 shell 語意的輸入？

`src/utils/bash/ast.ts` 的註解明確界定：這不是 sandbox，也不證明 command「無害」；它只證明 runtime 能否為每個 simple command 產生可信的結構。若不能，就回到保守的 `ask`，而不是猜測。

## 完整分析管線

實際流程有 early return、遞迴與 legacy fallback，並非一條永遠線性的管線：

```mermaid
flowchart TD
    A["Bash input"] --> B["BashTool<br/>Zod schema + validateInput"]
    B --> C["BashTool.checkPermissions"]
    C --> D["parser<br/>parseCommandRaw + parseForSecurityFromAst"]
    D -->|simple| E["parser<br/>SimpleCommand[] + semantic checks"]
    D -->|too-complex| F["rule matcher<br/>exact deny/ask/allow + deny fallback"]
    D -->|parse-unavailable| G["parser<br/>legacy shell-quote / split fallback"]
    E --> H{"operator / decomposition"}
    G --> H
    H -->|pipe| P["BashTool<br/>reconstruct segments + recursively re-check each"]
    H -->|&& / || / ; / ordinary leaves| I["rule matcher<br/>lower-level per-subcommand checks"]
    P --> Q["BashTool helper<br/>pipe-specific result aggregation"]
    I --> N["candidate normalization<br/>exact/prefix/wildcard"]
    Q -->|deny / ask| L
    Q -->|all allow| J
    N --> J["safety checks<br/>path, unsafe command, injection guards"]
    J --> K["suggestion generation<br/>narrow prefix or exact; otherwise none"]
    F --> L["PermissionResult"]
    K --> L
    L --> M["permission layer<br/>06a: generic precedence, mode, prompt"]
```

主要 source ordering 如下：

1. 通用層先用 `BashTool.inputSchema` parse input，再呼叫 `BashTool.checkPermissions()`；本文從已通過 schema 的 command-level 檢查開始。
2. `bashToolHasPermission()` 只 parse 一次，將同一 AST 交給 security walker 與 operator analysis。
3. `too-complex` 不進一般拆分：先尊重 exact deny/ask/allow 與 prefix/wildcard deny，否則直接 `ask` 且不產生 suggestion。
4. `simple` 先跑 `checkSemantics()`；通過後保存 AST-derived subcommands、redirects 與 `SimpleCommand[]`。
5. `parse-unavailable` 才走 legacy `tryParseShellCommand()`、`splitCommand_DEPRECATED()` 與 regex safety validators。Malformed syntax 直接 `ask`。
6. Operator analysis 先處理 unsafe structure 與 pipe。只有 pipe segments 會在重建並移除 segment output redirection 後，逐段遞迴回完整的 `bashToolHasPermission()`。
7. `&&`、`||`、`;` 等一般 compound/list 則使用 AST/legacy 拆出的 leaf subcommands，直接呼叫較低層的 `bashToolCheckPermission()`，再視需要進 `checkCommandAndSuggestRules()`，不是同一條 pipe recursion。
8. 兩條 aggregation 都是任一 deny 優先、全部 allow 才 allow；但一般 compound 與 pipe 對 ask/passthrough、suggestions 的聚合細節不同。
9. command-level `PermissionResult` 回到通用 permission layer；`passthrough` 不是 allow，通常會在 06a 的通用層成為 `ask`。

## BashTool 輸入與 PermissionResult

`BashTool` 的 model-facing schema 是 strict object，核心欄位為：

| 欄位 | command analysis 的意義 |
|---|---|
| `command: string` | 本文分析的原始 Bash 文字 |
| `timeout?: number` | 執行參數，不改變 permission rule 的 command text |
| `description?: string` | 顯示用途，不參與授權 |
| `run_in_background?: boolean` | 可因 feature gate 從 schema 移除 |
| `dangerouslyDisableSandbox?: boolean` | 影響是否使用 containment，不替代 permission |

內部 `_simulatedSedEdit` 明確從 model-facing schema 移除，避免模型把任意 file write 偽裝成 innocuous command。`validateInput()` 在此 snapshot 另會阻擋特定長時間 `sleep` 使用方式；通過後，`checkPermissions()` 直接呼叫 `bashToolHasPermission(input, context)`。

`PermissionResult` 在 Bash 層可為：

- `deny`：明確 rule、semantic 或 path branch 拒絕。
- `ask`：結構無法可信分析、安全檢查要求批准、ask rule 命中，或 compound 結果需要人工確認。
- `allow`：exact/prefix/wildcard allow、read-only/mode branch，或所有 subcommands 都 allow。
- `passthrough`：Bash 層沒有作最終裁決；回到 06a 的通用 permission layer 繼續。

這裡的 `decisionReason` 可能保存命中的 rule，也可能是 `subcommandResults` map，讓上層知道 compound command 中每一段為何 allow、ask 或 deny。

## shell parser 能確認什麼

`ParseForSecurityResult` 只有三種：

```text
simple           → commands: SimpleCommand[]
too-complex      → reason + optional nodeType
parse-unavailable
```

`SimpleCommand` 保存：

```text
argv[]      已解 quote 的 command 與 arguments
envVars[]   leading VAR=value assignments
redirects[] redirect operator、target、optional fd
text        原始 source span，供顯示與下游 string matcher 使用
```

`simple` 能證明的是：security walker 已用明示 allowlist 走完 AST，能為每個 leaf command 建立可信結構。它不能證明：

- binary 本身沒有副作用；
- path、network 或 OS resource 一定安全；
- allow rule 應該存在；
- command 應自動執行。

AST walker 會遞迴處理 `program`、`list`、`pipeline`、`redirected_statement`，辨識 `&&`、`||`、`|`、`;`、`&`、`|&` 與 newline。`&&`、`;` 可沿用前段已確定的 variable scope；`||`、pipe 與 background branch 會重設到 snapshot，避免把條件式或 subshell 內的 assignment 誤當成後段必然存在。

部分 command substitution 可被遞迴抽出：inner command 也加入 `commands[]`，outer argument 放入 placeholder，再分別做 permission check。這不表示所有 expansion 都可接受。Process substitution、無法解析的 parameter/arithmetic/brace expansion、未知 node type，或 runtime-determined command name 仍會轉成 `too-complex`。

`for_statement`、`if_statement`、`while_statement` 是高風險 shell control flow，但不是僅因 node type 就必然 `too-complex`。Walker 有專用 branch，會抽取 condition、iteration source 與各 branch/body 的 commands，並用 scope copy、unknown-value placeholder 等方式避免條件分支或 loop variable 汙染後續分析。若 body 只使用能靜態證明的內容，整體可回 `simple`；若 loop variable 被當作 bare path/flag、特殊變數繞過 assignment validation，或 branch scope 無法證明，才保守回 `too-complex`。

## simple、too-complex、parse-unavailable 的分流

`parseForSecurityFromAst()` 在信任 AST tokenization 前先做 parser differential pre-check：

- non-printable control characters；
- Unicode whitespace；
- backslash-escaped whitespace；
- zsh `~[` dynamic directory syntax；
- zsh `=cmd` expansion；
- quote 混入 brace expansion 的 obfuscation。

命中即為 `too-complex`。Parser 已載入但因 50ms timeout、50,000 node budget 或 panic 中止，也回 `too-complex`，不降級成較弱的 legacy parser。這個區分可避免 adversarial input 故意觸發 parser abort 後逃到 fallback。

`simple` 之後仍有 `checkSemantics()`。它針對 tokenizer 無法單靠語法辨識的行為做 argv-level 檢查，例如：

- `eval`、`source`、`exec`、`trap`、`enable` 等會重新解釋 arguments 的 builtin；
- zsh dangerous builtins；
- `jq system(...)` 與特定讀檔 flags；
- `env`、`timeout`、`nice`、`stdbuf` 等 wrapper 的可辨識 flag forms；
- array subscript 中可能被 shell 再次 arithmetic-evaluate 的內容；
- `/proc/*/environ`；
- newline + `#` 造成下游重新 tokenization desync。

`parse-unavailable` 表示 parser module/feature 不可用、command 為空或超過 parser 長度 gate 等「沒有 AST 結果」；它不是「已證明 command 複雜」。此 branch 先用 `tryParseShellCommand()` 檢查 malformed syntax，再走 legacy split 與 `bashCommandIsSafeAsync_DEPRECATED()`。因此：

```text
parser available + too-complex
  → checkEarlyExitDeny（exact deny/ask/allow；prefix/wildcard deny）
  → 若未命中，fail closed / ask

parser unavailable
  → legacy tryParseShellCommand
  → malformed syntax 時立即 ask，尚未進後面的 exact matching
  → parse 成功才繼續 legacy split / rule / safety checks
```

**版本限制**：`TREE_SITTER_BASH`、shadow mode、killswitch 與 command-injection env flag 會改變哪條 branch 成為 authoritative。本文描述此 commit 的 source ordering，不保證每個 build 都啟用相同 feature。

## compound command 如何拆分

AST path 優先使用每個 `SimpleCommand.text`；只有 `parse-unavailable` 才依賴 `splitCommand_DEPRECATED()`。Legacy splitter 會保留 quote、處理 line continuation、heredoc placeholder、operator token，並將可安全辨識的 output redirection 從 subcommand 文字移除；redirect target 仍由獨立 path validation 檢查。

以下是 pipe aggregation 的**真實原始碼節錄（abridged）**：

```ts
for (const segment of segments) {
  const segmentResult = await bashToolHasPermissionFn({
    ...input,
    command: segment.trim(),
  })
  segmentResults.set(segment.trim(), segmentResult)
}

if (deniedSegment) {
  return { behavior: 'deny', /* decisionReason: subcommandResults */ }
}
if (allAllowed) {
  return { behavior: 'allow', /* decisionReason: subcommandResults */ }
}
return { behavior: 'ask', /* collected suggestions */ }
```

輸入只是在 pipe path 中重建出的 segments；每段不是直接做字串 prefix check，而是重新進完整 Bash permission flow。輸出以 deny 優先，只有全部 allow 才 allow，其餘 ask。安全理由是：`git status | curl ...` 不能因第一段安全就放行第二段。

一般 `&&`、`||`、`;` 不走上述 helper。`bashToolHasPermission()` 會取得 AST-derived leaf spans（legacy 時才用 splitter），先以 `bashToolCheckPermission()` 對每個 subcommand 做 exact、deny/ask、path、allow、mode/read-only 檢查；尚未作最終決定的 leaf 才進 `checkCommandAndSuggestRules()`，最後在同一函式內聚合。

實際 branch 還包含：

- subshell：AST walker 有專用 branch，會以 isolated scope 抽取 inner commands，因此可先得到 `simple`；若沒有更早的 deny short-circuit，後續 operator analysis 看到 `hasSubshell` 後會走 unsafe-compound `ask`，不產生 suggestion；
- command group：若 parser 產生 `compound_statement`，security walker 沒有同等的 allowlisted collector branch，會落入 `too-complex`；此時先走 `checkEarlyExitDeny()`，所以 exact deny/ask/allow 或 full-command prefix/wildcard deny仍可能先返回，未命中才 conservative `ask`；
- pipe：保留 quote 拆 segment，移除 output redirects 後逐段遞迴；
- pipe segments 全 allow 後：仍回頭驗證原 command 的 redirect 與 path，避免 redirect 因拆分而消失；
- 多個 `cd`，或同一 compound 中同時出現 `cd` 與 `git`：保守 `ask`；
- legacy split 出過多 subcommands：超過 cap 直接 `ask`；
- exact allow 可在特定保守 branch 明確放行完整原 command，但 wildcard 不會在未拆分原字串上匹配。

## exact、prefix、wildcard 規則如何匹配

`bashPermissionRule` 委派給 shared `parsePermissionRule()`。以下為真實 contract 的**節錄（abridged）**：

```ts
const prefix = permissionRuleExtractPrefix(rule)
if (prefix !== null) return { type: 'prefix', prefix }
if (hasWildcards(rule)) return { type: 'wildcard', pattern: rule }
return { type: 'exact', command: rule }
```

輸入是 `ruleContent` 字串；結尾 `:*` 優先解析成 legacy prefix，其他未 escaped 的 `*` 是 wildcard，否則為 exact。輸出是 discriminated union，後續 matcher 不再靠猜測字串形狀。

三種語意：

| rule style | 例子 | matching semantics |
|---|---|---|
| exact | `git status` | candidate 必須完全相同；exact phase 會試原 command 與移除 output redirect 的版本 |
| prefix | `git:*`、`git status:*` | candidate 等於 prefix，或以 `prefix + " "` 開始；word boundary 防止 `ls:*` 命中 `lsof` |
| wildcard | `git * --stat` | pattern 轉成 anchored regex；Bash case-sensitive；`\*` 是 literal `*`，`\\` 是 literal backslash |

只有一個、且位於結尾 `" *"` 的 wildcard 有特殊相容語意：`git *` 同時匹配 `git` 與 `git add`。多 wildcard 不套用這個 optional-tail 規則。

Prefix/wildcard allow 只在 command 已拆成 atomic subcommand 後使用；若 candidate 仍是 compound，allow matcher 拒絕命中。Deny/ask 則刻意可在 compound context 匹配，避免把 denied command 包進 compound 就繞過。

Matcher 另支援 bare `xargs <prefix>`：例如 `Bash(rm:*)` 可命中 `xargs rm file`，但 `xargs -n1 rm` 不會被這個 shortcut 誤判，因為 natural word boundary 不成立。

## env var 與 wrapper stripping

Rule matching 會先移除可安全辨識的 output redirection，再產生候選：

```text
原 command
移除 output redirect
移除 safe leading env assignments
移除 safe wrappers
deny/ask 時再做 aggressive env stripping 與 fixed-point iteration
```

Safe env allowlist 只包含不會選擇另一個 binary、載入 module 或改變重要 shell 行為的項目，例如 `GOOS`、`NODE_ENV`、`NO_COLOR`、`LANG`。Source 明確禁止把 `PATH`、`LD_PRELOAD`、`DYLD_*`、`PYTHONPATH`、`NODE_OPTIONS`、`HOME`、`BASH_ENV` 等加入 allowlist。

`stripAllLeadingEnvVars()` 的核心為以下**節錄（abridged）**：

```ts
while (stripped !== previousStripped) {
  previousStripped = stripped
  stripped = stripCommentLines(stripped)
  const m = stripped.match(ENV_VAR_PATTERN)
  if (!m) continue
  if (blocklist?.test(m[1])) break
  stripped = stripped.slice(m[0].length)
}
return stripped.trim()
```

輸入是 command 與 optional blocklist；每次只移除一個完整、無 active expansion 的 leading assignment，直到沒有變化。若 variable name 命中 blocklist，剝除立即停止。這讓 deny/ask 可把 `FOO=bar rm ...` 還原成 `rm ...`，又讓 `excludedCommands` 保留 `PATH`、`LD_*`、`DYLD_*` 這類 binary-hijack signal。

Rule matcher 的 wrapper stripping 只接受可具體建模的：

```text
timeout、time、nice、stdbuf、nohup
```

它先剝 safe env，再剝 wrapper，且 phase 2 不再剝 wrapper 後面的 env assignment。原因是：

```text
FOO=bar timeout 30 cmd   # FOO 是 shell assignment
timeout 30 FOO=bar cmd   # FOO=bar 是 timeout 要 exec 的 command name
```

把第二種也剝掉會讓 matcher 看見與 shell 實際執行不同的 command。

Deny/ask 的候選生成較 aggressive：`stripAllLeadingEnvVars()` 與 `stripSafeWrappers()` 對所有新候選反覆套用至 fixed point，所以 `nohup FOO=bar timeout 5 claude` 最後可得到 `claude`，讓 deny 不易被層層 prefix 繞過。Allow 不做 arbitrary env stripping，因為 `DOCKER_HOST=evil docker ps`、`PYTHONPATH=... python` 等可能改變真正執行語意。

### 正規化對照表

前六列假設 AST parser 可用；最後一列刻意對照 parser available 與 unavailable 兩條 malformed-syntax branch。Rule outcome 仍取決於實際設定，因此只列 source 能確定的 candidate 與條件。

| raw command | parser / decomposition | candidate 或 stripping | stripping 停止點 | 可匹配 rule style 與原因 |
|---|---|---|---|---|
| `git status` | `simple`；一個 leaf，argv 約為 `["git","status"]` | `git status` | 無 prefix 可剝 | exact `git status`、prefix `git:*` / `git status:*`、wildcard `git *` |
| `git status && curl example.com` | `simple`；兩個 leaf，由一般 compound path 做較低層 per-subcommand checks，不走 pipe recursion | `git status`、`curl example.com` | operator 不屬於任何 leaf | 每段可各自 exact/prefix/wildcard；allow prefix 不直接匹配整條 compound |
| `FOO=bar bazel run //target` | `simple`；assignment 與 argv 分離，但下游 rule matcher 仍使用 source span | allow candidates 保留原文；deny/ask fixed point 可得 `bazel run //target` | allow 在 `FOO` 停止，因 `FOO` 不在 safe allowlist | exact 原文可匹配；deny/ask 的 `bazel:*` / wildcard 可匹配；一般 allow `bazel:*` 不可藉 arbitrary `FOO` 命中 |
| `timeout 30 bazel test //...` | `simple`；semantic check 可辨識 wrapper；一個 wrapped command | 原文與 `bazel test //...` | duration/flags 必須符合 allowlisted grammar；未知 flag/value fail closed | `bazel test:*` allow/deny/ask 可匹配 stripped candidate；自動 suggestion 對原文第二 token 為 `30`，通常退回 exact |
| `RUN=/tmp/tool python3 script.py` | `simple`；leading assignment | deny/ask 可得 `python3 script.py`；allow 保留 `RUN=...` | allow 在非-safe `RUN` 停止 | exact 原文；deny/ask 可命中 `python3:*`；allow `python3:*` 不命中 |
| `sh -c "..."` | 語法上可為 `simple`；shell body 是 argument，不代表其內容已被 rule parser 展開 | 通常維持原文；`sh` 不是 safe wrapper | 不剝 `sh` | exact 或使用者手寫 wildcard/prefix 可能匹配；suggestion 拒絕產生 `sh:*`，auto-mode cleanup 也視 broad shell rule 為 dangerous |
| malformed shell syntax | parser available：通常為 `too-complex` / `Parse error`；parser unavailable：legacy parse failure | 兩條 branch 都不信任 decomposition；available branch 仍可先檢查原 command 的 early-exit rules，legacy malformed branch 不產生後續 matching candidates | available branch 在 early-exit rule 或 conservative ask 停止；legacy malformed branch 在 syntax check 立即停止 | 只有 `too-complex` branch 可命中 exact deny/ask/allow 與 prefix/wildcard deny；legacy malformed branch 會在 exact matching 前直接 `ask` |

## unsafe command 與保守回退

Source 將「不能可靠 tokenise」與「tokenise 成功但語意危險」分開：

```text
parseForSecurity / AST allowlist  → 結構可信度
checkSemantics                   → argv-level shell escape hatches
bashCommandIsSafeAsync legacy    → parser unavailable 時的 differential/regex guards
path/sed/read-only checks        → command-specific constraints
```

主要 fail-closed 行為：

- unknown AST node、parse error、control character、Unicode whitespace、special expansion 無法靜態求值：`too-complex`；
- parser abort：`too-complex`，不 legacy downgrade；
- legacy malformed syntax：在 exact matching 前直接 `ask`；
- subshell 若先被 walker 證明為 `simple`：後續 unsafe-operator branch `ask` 且不建議 rule；
- command group / `compound_statement` 若成為 `too-complex`：先檢查 exact deny/ask/allow 與 full-command deny，未命中才 `ask`；
- dangerous semantic builtin 或 wrapper flag 無法定位 wrapped command：先執行 deny enforcement，再 `ask`；
- safety validator 發現 injection/misparsing concern：`ask`，`suggestions: []`；
- compound 任一 subcommand deny：整體 deny；
- compound 沒有全部 allow：不把部分 allow 誤當整體 allow。

在 parser available 的 `too-complex` branch，exact rule 是少數有意識的 escape hatch：使用者可精確允許一條完整複雜 command；但 broad prefix/wildcard 不會在未拆分原 command 上自動放行，deny 也不會被 fallback 降級成 ask。這不適用於 legacy malformed-syntax early return：該 branch 在後續 exact matching 前已回 `ask`。

## approval suggestion 如何避免過度授權

Rule matching 與 approval suggestion 的安全目標不同：

- matching 要判斷「既有規則是否適用」，deny/ask 因而需要 aggressive normalization；
- suggestion 要提出「未來仍會自動 allow 的新規則」，因此必須更窄，不能因這次 command 看似合理就授予整個 shell/wrapper。

`getSimpleCommandPrefix()` 的**真實原始碼節錄（abridged）**：

```ts
while (i < tokens.length && ENV_VAR_ASSIGN_RE.test(tokens[i]!)) {
  const varName = tokens[i]!.split('=')[0]!
  if (!SAFE_ENV_VARS.has(varName) && !isAntOnlySafe) return null
  i++
}
const remaining = tokens.slice(i)
if (remaining.length < 2) return null
if (!/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(remaining[1]!)) return null
return remaining.slice(0, 2).join(' ')
```

輸入是原 command；它只跳過 safe env assignments，且第二 token 必須像 `commit`、`run`、`compose`，不能是 flag、path、URL、filename 或 number。輸出才會成為 `${prefix}:*`；否則退回 exact suggestion。安全理由是避免把 `rm -rf ...` 建議成 `rm:*`，也避免建議一條 matcher 實際永遠無法命中的規則。

`getFirstWordPrefix()` 只是 UI editable fallback，不是 backend 自動 suggestion。它額外拒絕：

```text
sh、bash、zsh、fish、dash、cmd、powershell、pwsh
env、xargs、nice、stdbuf、nohup、timeout、time
sudo、doas、pkexec
```

`sh:*` / `bash:*` 可透過 `-c` 執行任意 shell program；`env:*`、`sudo:*` 與 exec-style wrappers 也能把任意後續 command 放在 prefix 之後。因此 source 寧可建議 exact `sh -c "..."`，也不自動產生可泛化成 arbitrary code execution 的 prefix。

Heredoc 與 multiline command 另有穩定性處理：嘗試取 heredoc 前的窄 prefix，或第一行 prefix；若無法安全抽取，仍回 exact。

Suggestion aggregation 也分兩條路：

- 一般 `&&`、`||`、`;` compound aggregation 會從各 subcommand 抽取 rules，以字串表示去重，再只保留左側前 `MAX_SUGGESTED_RULES_FOR_COMPOUND` 筆。
- Pipe 的 `segmentedCommandPermissionResult()` 只把非-allow segment 的 `suggestions` 依序 `push(...result.suggestions)`；該 helper 本身沒有套用上述 rule-level dedup 或相同 cap。

## dangerous permission cleanup

這一節只說明 command rule 如何被辨識為過度寬廣；mode transition 與通用 precedence 詳見 06a。

`permissionSetup.ts` 有兩組相關檢查：

1. `findOverlyBroadBashPermissions()` 找 tool-level `Bash` / `Bash(*)` / `Bash()`；parser 會把它們正規化成沒有 `ruleContent` 的 whole-tool allow，等價於允許所有 Bash command。
2. `findDangerousClassifierPermissions()` 在 auto mode 找會先於 classifier 放行 arbitrary code 的 allow rules，例如 broad `python:*`、`node:*`、`bash:*`、`sh:*`、`env:*`、`xargs:*`、`sudo:*` 及其 wildcard variants。

`stripDangerousPermissionsForAutoMode()` 會把可更新來源中的危險 allow rules 從 in-memory context 移除並 stash，離開 auto mode 再恢復。`removeDangerousPermissions()` 不會修改不可作為 update destination 的 `flagSettings`、`policySettings`、`command` source。

Download/execute 規則有版本與環境限制：在此 snapshot，`curl`、`wget`、`gh`、`git` 等 broad prefix 被加入 `DANGEROUS_BASH_PATTERNS` 的部分是 `USER_TYPE === "ant"` 的 internal empirical policy，不應推廣成所有 external build 都會 cleanup 的保證。跨平台 interpreter、shell、package runner 與 remote command wrapper 則是 shared dangerous patterns。

## excludedCommands 為何不是安全邊界

Source 的責任切分是：

```text
permission decides authorization
excludedCommands only influences whether an authorized command skips containment
```

`shouldUseSandbox()` 只有在 sandbox 已啟用、沒有合法 explicit override、command 存在，且 `containsExcludedCommand()` 沒命中時才回 true。這裡不解釋 containment 如何運作；關鍵是 `excludedCommands` 不會把未授權 command 變成已授權。

`containsExcludedCommand()` 重用 permission rule parser 與 matcher：

- compound command 先拆成 subcommands，逐段檢查；
- 每段從原文開始，同時嘗試 env stripping 與 safe wrapper stripping；
- 新候選反覆加入直到 fixed point；
- exact、prefix、wildcard 使用與 permission rule 相同的基本語意；
- parse failure 時 fallback 為 `[original command]`，避免 rendering/selection crash；
- `BINARY_HIJACK_VARS = /^(LD_|DYLD_|PATH$)/` 命中時停止 env stripping，避免把「其實會換 binary/library」的 prefix 藏掉。

例如 `timeout 300 FOO=bar bazel run` 可經 fixed point 得到 `bazel run`；但 `PATH=/tmp/bin bazel run` 在 `PATH` 停止。這仍只是 convenience matcher。繞過它的後果是 command 沒有如預期跳過 containment，而不是 permission authorization 被繞過；source 也明示 export-then-command 等形式可能繞過此 heuristic，並不把它視為 security-boundary failure。

## 走一遍具體案例

以下案例為了得到 deterministic outcome，明示假設：parser 可用、沒有 prompt classifier 額外規則、path checks 無額外阻擋，且只列出的 Bash rules 存在。

### 案例一：simple exact allow

```text
raw input:
  git status

parser result:
  simple
  commands = [{ argv: ["git", "status"], envVars: [], redirects: [] }]

normalized candidates:
  "git status"

matched/unmatched rules:
  exact allow "git status" 命中

safety result:
  checkSemantics 通過；exact allow 在後續 aggregate 中保留

final PermissionResult:
  allow，updatedInput 為原 input，decisionReason.type = "rule"
```

### 案例二：compound command，混合 rule outcome

規則：

```text
allow: git status
deny:  curl:*
```

流程：

```text
raw input:
  git status && curl example.com

parser result:
  simple；兩個 leaf commands
  這是一般 && compound path，不是 pipe segment recursion

normalized candidates:
  "git status"
  "curl example.com"

matched/unmatched rules:
  第一段命中 exact allow
  第二段命中 prefix deny "curl:*"

safety result:
  結構與 semantics 可分析；不需要靠 legacy injection validator

final PermissionResult:
  deny
  decisionReason.type = "subcommandResults"
  原因是一般 compound aggregation 中任一 subcommand deny 優先於其他 allow
```

### 案例三：safe env + wrapper-prefixed command

規則：

```text
allow: bazel test:*
```

流程：

```text
raw input:
  NO_COLOR=1 timeout 30 bazel test //pkg:all

parser result:
  simple
  envVars 含 NO_COLOR=1；argv 可辨識 timeout wrapper 與 wrapped bazel

normalized candidates:
  原文
  "bazel test //pkg:all"

matched/unmatched rules:
  prefix allow "bazel test:*" 命中 stripped candidate

safety result:
  NO_COLOR 在 SAFE_ENV_VARS
  timeout duration 30 符合 allowlisted grammar
  wrapped command semantics 通過

final PermissionResult:
  allow，decisionReason 指向 matching allow rule
```

若改成 `RUN=/tmp/tool timeout 30 bazel test //pkg:all`，allow normalization 會停在非-safe `RUN`；同一條 `bazel test:*` 不再因此自動 allow。Deny/ask matching 則仍可 aggressive strip `RUN`。

### 案例四：unparseable / too-complex 的保守路徑

```text
raw input:
  echo "unterminated

parser result:
  parser 可用：too-complex，reason 通常為 Parse error
  parser 不可用：legacy tryParseShellCommand failure

normalized candidates:
  不信任拆分；保留原 command

matched/unmatched rules:
  parser 可用 / too-complex：
    先檢查原 command 的 exact deny/ask/allow 與 prefix/wildcard deny；
    此例假設全部未命中
  parser 不可用 / legacy malformed：
    syntax failure 立即返回，不執行後面的 exact matching

safety result:
  兩條 branch 都不進一般 decomposition / safety aggregation；
  too-complex 是 early-rule 後 fail closed，legacy malformed 是 syntax check 後 fail closed

final PermissionResult:
  parser 可用且 early rules 未命中：ask，suggestions: []
  parser 可用且 exact rule 命中：依該 exact deny / ask / allow 結果返回
  parser 不可用且 legacy syntax parse 失敗：ask，未進 exact matching
```

## 證據、限制與設計取捨

- **證據**：CodeGraph call relation 顯示 `BashTool.checkPermissions → bashToolHasPermission → checkCommandOperatorPermissions / bashToolCheckPermission / checkCommandAndSuggestRules`；pipe path 再由 `segmentedCommandPermissionResult` 遞迴回 `bashToolHasPermission`。
- **證據**：`parseForSecurityFromAst()` 明確區分 parser unavailable 與 parser abort；後者回 `too-complex`。
- **證據**：`matchingRulesForInput()` 對 deny/ask 設定 `stripAllEnvVars: true`，allow 沒有；候選 fixed-point loop 與 allow compound rejection 都在 matcher source 中。
- **證據**：`getSimpleCommandPrefix()` 與 `BARE_SHELL_PREFIXES` 說明 suggestion 比 matching 更保守；它們不是同一套 normalization policy。
- **證據**：`shouldUseSandbox.ts` 的 source comment 直接聲明 `excludedCommands` 是 user-facing convenience，不是 security boundary。
- **版本限制**：tree-sitter feature、shadow mode、classifier、internal `USER_TYPE` 與 killswitch 會改變 active branch 或 cleanup set。
- **推論**：表格中的 argv 省略 parser 內部 placeholder 與 source byte offsets；這不改變列出的 rule-matching結論。
- **尚未確認**：此 read-only snapshot 未包含可直接執行的完整 test harness；本文的 deterministic 案例以 source branch、call relation 與 source comments 為證，未宣稱做過 runtime integration experiment。
- 設計取捨是「可理解才泛化」：exact rule 可表達使用者對完整字串的明確決定；prefix/wildcard 只有在 atomic command 與 narrow suggestion 可成立時才泛化。

## 源碼入口

| 檔案 | 主要 symbols / 責任 |
|---|---|
| `src/tools/BashTool/BashTool.tsx` | `fullInputSchema`、`inputSchema`、`validateInput`、`BashTool.checkPermissions` |
| `src/tools/BashTool/bashPermissions.ts` | `bashToolHasPermission`、`bashToolCheckExactMatchPermission`、`bashToolCheckPermission`、`checkCommandAndSuggestRules`、`filterRulesByContentsMatchingInput`、`stripSafeWrappers`、`stripAllLeadingEnvVars`、`getSimpleCommandPrefix`、`getFirstWordPrefix` |
| `src/tools/BashTool/bashCommandHelpers.ts` | `checkCommandOperatorPermissions`、`bashToolCheckCommandOperatorPermissions`、`segmentedCommandPermissionResult` |
| `src/tools/BashTool/bashSecurity.ts` | `bashCommandIsSafeAsync_DEPRECATED` 與 legacy validators |
| `src/tools/BashTool/shouldUseSandbox.ts` | `containsExcludedCommand`、`shouldUseSandbox`；只決定 containment selection |
| `src/utils/bash/ast.ts` | `ParseForSecurityResult`、`parseForSecurity`、`parseForSecurityFromAst`、`walkProgram`、`collectCommands`、`checkSemantics` |
| `src/utils/bash/parser.ts` | `parseCommandRaw`、`PARSE_ABORTED`、feature/length gate |
| `src/utils/bash/bashParser.ts` | pure-TypeScript parser、50ms timeout、50,000 node budget |
| `src/utils/bash/commands.ts` | `splitCommandWithOperators`、`splitCommand_DEPRECATED`、redirect/operator fallback |
| `src/utils/bash/treeSitterAnalysis.ts` | quote context、compound structure、dangerous pattern extraction |
| `src/utils/permissions/shellRuleMatching.ts` | `ShellPermissionRule`、`parsePermissionRule`、`matchWildcardPattern`、shared suggestions |
| `src/utils/permissions/permissionSetup.ts` | dangerous / overly broad Bash permission detection、cleanup 與 restore |
