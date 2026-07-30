# 06a - Permission Decision：tool_use 如何變成 allow / ask / deny

> Source snapshot
>
> 本文依據 Claude Code source commit `712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf` 重建。討論範圍是 runtime 的 permission decision、互動批准與相關狀態；sandbox 在此只作為 permission flow 的一個判斷輸入。作業系統層級 containment、namespace、seccomp、檔案系統與網路隔離不在本文範圍內。

## 這項機制真正解決什麼問題

模型輸出 `tool_use` 只表示「想執行某個工具與輸入」，並不等於 runtime 已授權。Permission pipeline 要把同一個請求放進數個彼此獨立的約束中：

- 管理者、設定檔、CLI、session 是否已有 whole-tool 或 content-level 規則。
- 工具是否能理解輸入內容並辨識額外風險，例如 Bash 子命令、工作目錄外的檔案或敏感路徑。
- 當前 `permission mode` 能否把尚未匹配的動作直接放行、交給 classifier，或禁止詢問。
- 當結果仍是 `ask` 時，這個 execution context 是否真的能顯示 UI，或必須交給 hook、SDK、stdio、MCP permission tool。
- 等待規則、classifier、hook 或使用者期間，請求是否已被 abort。

所以它不是單一 allowlist，也不是一個「是否跳出對話框」的布林值。核心設計是：先保留工具自己的語意，再由通用層決定規則與 mode 的優先順序，最後由互動層處理批准、拒絕和設定更新。

## 先看完整裁決流程

先用三層定位主要 symbols：`useCanUseTool()` 或 headless `CanUseToolFn` 是入口；`hasPermissionsToUseToolInner()` 依序處理 abort、`getDenyRuleForTool()`、`getAskRuleForTool()`、sandbox ask 例外、`Tool.checkPermissions()`、bypass 與 `toolAlwaysAllowedRule()`；外層 `hasPermissionsToUseTool()` 再處理 `dontAsk`、auto、prompt availability，以及 `recordSuccess()` / `recordDenial()` / `persistDenialState()`。最後，互動 UI、`StructuredIO` 或 permission prompt tool 才解決仍為 `ask` 的 `PermissionDecision`。

以下是依照 early return 次序整理的**偽代碼**，不是原始碼：

```text
permissionDecision(tool, input, context):
  # A. inner permission decision
  inner():
    if abortController.signal.aborted:
      throw AbortError

    if whole-tool deny rule matches:
      return deny(rule)

    if whole-tool ask rule matches:
      if not (Bash and sandbox enabled and autoAllowBashIfSandboxed and shouldUseSandbox(input)):
        return ask(rule)
      # 只在這個例外中繼續；後面的 Bash checkPermissions 再判斷內容

    toolResult = passthrough
    try:
      parsed = tool.inputSchema.parse(input)
      toolResult = await tool.checkPermissions(parsed, context)
    catch AbortError or APIUserAbortError:
      rethrow
    catch other error:
      log; keep passthrough

    if toolResult is deny:
      return deny
    if tool requires user interaction and toolResult is ask:
      return ask
    if toolResult is ask caused by explicit content ask rule:
      return ask
    if toolResult is ask caused by safetyCheck:
      return ask

    refresh app state
    if mode is bypassPermissions
       or mode is plan and bypass was available at launch:
      return allow(mode, updatedInput)

    if whole-tool allow rule matches:
      return allow(rule, updatedInput)

    if toolResult is passthrough:
      return ask
    return toolResult

  innerResult = await inner()

  # B. outer mode transformation；不屬於 inner()
  outerTransform(result):
    if result is ask and mode is dontAsk:
      return { decision: deny(mode=dontAsk) }

    if result is ask and auto classifier path is active:
      enforce non-classifier safety exceptions
      if acceptEdits fast path allows:
        return { decision: allow, autoOutcome: success }
      if safe-tool allowlist allows:
        return { decision: allow, autoOutcome: success }

      classifierResult = run classifier with abort signal
      if classifier allows:
        return { decision: allow, autoOutcome: success }
      if classifier blocks normally:
        return {
          decision: provisional classifier deny,
          autoOutcome: blocked(classifier reason),
        }
      # transcript-too-long 的 headless 分支可直接 throw AbortError
      return { decision: fallback ask / unavailable deny }

    if result is ask and permission prompts must be avoided:
      run PermissionRequest hooks
      if a hook decides: return { decision: hook allow / deny }
      return { decision: deny(asyncAgent) }

    return { decision: result }

  # C. post-decision state bookkeeping；與 mode transformation 分開
  bookkeepDecision(innerResult, transformed):
    if innerResult is allow and current mode is auto
       and consecutiveDenials > 0:
      newState = recordSuccess()
      persistDenialState(newState)
      # 清除非零 consecutiveDenials，保留 totalDenials

    if transformed.autoOutcome is success:
      newState = recordSuccess()
      persistDenialState(newState)

    if transformed.autoOutcome is blocked(reason):
      newState = recordDenial()
      persistDenialState(newState)
      if denial limit is reached:
        replace provisional deny with fallback ask
        or throw AbortError when prompts are unavailable

  # source order：inner 已 allow 時，先做 C，直接返回；
  # 否則先由 B 產生 mode/auto outcome，再由 C 更新狀態與完成 final decision。
  if innerResult is allow:
    bookkeepDecision(innerResult, none)
    finalResult = innerResult
  else:
    transformed = outerTransform(innerResult)
    bookkeepDecision(innerResult, transformed)
    finalResult = transformed.decision

caller:
  if finalResult is allow or deny: resolve it
  if finalResult is ask:
    interactive UI, coordinator/swarm handler, stdio/SDK，
    or a configured permission prompt tool resolves the request
```

這個切分很重要：`dontAsk` 不是 `hasPermissionsToUseToolInner()` 的一部分；auto classifier 與 denial tracking 也在 outer function，但 state bookkeeping 仍是獨立責任。Source 的實際順序是：inner 已 allow 時先重設 auto 的連續拒絕並返回；inner ask 進 auto 時，則在 classifier allow/block 已產生後更新 denial state，再組出 final allow、deny、fallback ask 或 abort。把這些全塞進 inner 或把 bookkeeping 說成 UI presentation，都會錯置 early return 與狀態變更時點。

### 原始碼摘錄 1：abort、deny、ask、tool check 的順序

```ts
// abridged from hasPermissionsToUseToolInner()
if (context.abortController.signal.aborted) {
  throw new AbortError()
}
const denyRule = getDenyRuleForTool(appState.toolPermissionContext, tool)
if (denyRule) return { behavior: 'deny', /* rule provenance */ }
const askRule = getAskRuleForTool(appState.toolPermissionContext, tool)
if (askRule && !canSandboxAutoAllow) {
  return { behavior: 'ask', /* rule provenance */ }
}
toolPermissionResult = await tool.checkPermissions(parsedInput, context)
```

它依序讀取 abort signal、whole-tool deny/ask rule 與工具回傳值；選中的 branch 直接產生 `PermissionDecision`。順序的效果是 deny 不會被 allow mode 蓋過，whole-tool ask 通常也不會先落到工具內容判斷。唯一例外是符合 sandbox auto-allow 條件的 Bash，讓流程繼續到 Bash 的 `checkPermissions()`；這裡只確認後續 permission layer，並不代表本文要解釋 OS containment。

## 輸入、輸出與關鍵狀態

### `ToolPermissionContext`

`ToolPermissionContext` 是 permission check 的唯讀快照，主要欄位如下：

| 欄位 | 誰讀取 | 誰改變 | 用途 |
|---|---|---|---|
| `mode` | 通用層與各工具的 `checkPermissions()` | 初始化、`PermissionUpdate.setMode`、mode transition | 決定 unmatched action 要 ask、auto classify 或 bypass |
| `alwaysAllowRules` / `alwaysDenyRules` / `alwaysAskRules` | whole-tool matcher 與各工具的 content matcher | settings/CLI 初始化、使用者或 hook 的 `PermissionUpdate` | 按 source 保存規則與 provenance |
| `additionalWorkingDirectories` | filesystem/path permission | 初始化、`addDirectories` / `removeDirectories` | 擴充可讀寫工作範圍 |
| `isBypassPermissionsModeAvailable` | inner 的 plan 特例、mode 切換驗證 | 啟動時依 CLI、feature gate、settings 決定 | 記錄本 session 是否有合法 bypass 能力 |
| `isAutoModeAvailable` | mode UI/transition | 啟動與 auto gate 檢查 | 表示 auto 是否可用 |
| `strippedDangerousRules` | auto mode transition | `stripDangerousPermissionsForAutoMode()` / `restoreDangerousPermissions()` | 暫存會繞過 classifier 的危險 allow rules |
| `shouldAvoidPermissionPrompts` | outer function | async/subagent context 建立時 | 先跑 `PermissionRequest` hooks，無決策時 auto-deny |
| `awaitAutomatedChecksBeforeDialog` | `useCanUseTool()` | 可顯示 prompt 的 background/coordinator context | 先等待 hook/classifier，再考慮打擾使用者 |
| `prePlanMode` | plan transition | `prepareContextForPlanMode()` / transition | 離開 plan 時恢復原 mode，並判斷 plan 是否帶著 auto/bypass 語意 |

`ToolUseContext` 另外提供 `getAppState()`、`setAppState()`、`abortController`、tool list、message history 和 agent metadata。Inner function 在進入 mode 判斷前再次呼叫 `getAppState()`，避免長時間 `checkPermissions()` 後仍使用舊 mode。

### `PermissionResult` 與 `PermissionDecision`

`Tool.checkPermissions()` 回傳 `PermissionResult`：它比最終型別多一個 `passthrough`。`passthrough` 的意思不是 allow，而是「工具沒有在自己的層級作最終裁決，請通用層繼續」。Inner function 最後會把仍未處理的 `passthrough` 轉成 `ask`。

`PermissionDecision` 只有三種：

- `allow`：可帶 `updatedInput`、`userModified`、`decisionReason`。
- `ask`：有 prompt `message`，也可帶 `updatedInput`、`suggestions`、classifier metadata、blocked path。
- `deny`：有 `message` 與必要的 `decisionReason`。

`decisionReason` 保存裁決 provenance，包括 `rule`、`mode`、`hook`、`classifier`、`safetyCheck`、`asyncAgent`、`permissionPromptTool` 等。這使 UI、analytics 與錯誤訊息不必由 `behavior` 猜原因。

### Rule source、provenance 與 precedence

`PermissionRule` 同時保存：

```text
source + ruleBehavior + { toolName, optional ruleContent }
```

Source 枚舉順序是 `userSettings → projectSettings → localSettings → flagSettings → policySettings → cliArg → command → session`。同一 behavior 內，matcher 以此順序找第一個匹配規則，因此 `decisionReason.rule` 能指出實際命中的來源。

但跨 behavior 的 precedence 不是「最後來源覆蓋前面來源」。真實執行順序是：

```text
whole-tool deny
> whole-tool ask
> tool-level deny / explicit content ask / safety ask
> bypass
> whole-tool allow
> unmatched ask
```

因此低來源層級的 deny 仍可早於其他來源的 allow 返回。Policy/flag/command 規則不可由一般 UI 刪除；user/project/local 可持久化，CLI/session 只改記憶體。工具帶 `ruleContent` 的規則不會被 whole-tool matcher 命中，而是由工具自己的 `checkPermissions()` 解讀。

### `PermissionUpdate`

`PermissionUpdate` 是狀態變更命令，而不是裁決本身：

- `addRules`、`replaceRules`、`removeRules`
- `setMode`
- `addDirectories`、`removeDirectories`

Destination 是 `userSettings`、`projectSettings`、`localSettings`、`session` 或 `cliArg`。只有前三者由 `persistPermissionUpdates()` 寫入 settings；所有 destination 都會經 `applyPermissionUpdates()` 立即更新目前 `ToolPermissionContext`。

### Denial tracking 與 abort controller

Auto classifier 使用 `DenialTrackingState`：

```text
consecutiveDenials
totalDenials
```

上限是連續 3 次或 session 累計 20 次。Classifier block 先 `recordDenial()` 再檢查是否應 fallback；成功 allow 只清零 `consecutiveDenials`，保留 `totalDenials`。一般 agent 寫回 app state；`setAppState` 無效的 async subagent 改用 `localDenialTracking` 原地同步。

`AbortController` 則跨越 inner check、classifier、hook、UI 與 headless prompt tool。它不是一個 permission behavior：abort 通常以 `AbortError` / `APIUserAbortError` 傳播，到了 UI adapter 才被轉成 cancellation decision；自訂 permission prompt tool 甚至會用 `Promise.race()` 與 abort signal 競速。

## 啟動時如何建立 ToolPermissionContext

`initializeToolPermissionContext()` 的建立順序是：

1. 解析 `--allowed-tools` / `--disallowed-tools`，並正規化 legacy tool names。
2. 若指定 base tools，把 default preset 中不在 base set 的工具追加到 CLI deny rules。
3. 建立 `additionalWorkingDirectories`；若 `PWD` 是原始 cwd 的 symlink，加入一筆 `source: session`。
4. 檢查 bypass 是否可用：必須是要求 `bypassPermissions` 或允許 dangerous skip，且未被 feature gate 或 settings 禁用。
5. `loadAllPermissionRulesFromDisk()` 讀入 user/project/local/flag/policy 規則。
6. 在 auto mode 偵測會繞過 classifier 的危險 shell allow rules；另外針對特定 build 偵測 overly broad Bash/PowerShell 規則。
7. 先建立含 CLI allow/deny 的 context，再以 `applyPermissionRulesToPermissionContext()` 疊加 disk rules。
8. 合併 settings 的 `permissions.additionalDirectories` 與 `--add-dir`，驗證後以 `addDirectories(destination: cliArg)` 加入 context；無效設定產生 warning。

進入 auto 不只是把 `mode` 改成 `auto`。`transitionPermissionMode()` 會呼叫 `stripDangerousPermissionsForAutoMode()`，移除並暫存例如可能直接繞過 classifier 的廣泛 allow rule；離開使用 classifier 的 mode 時再由 `restoreDangerousPermissions()` 恢復。Plan mode 也會保存 `prePlanMode`，並依設定決定是否在 plan 期間啟用 auto。

**版本限制**：上述 dangerous-rule cleanup 受 `TRANSCRIPT_CLASSIFIER` feature 與 build/runtime gate 控制；本文只描述此 snapshot 中可見的分支，不保證所有發行通道都啟用相同功能。

## tool_use 前的真實裁決順序

### 1. Early abort

`hasPermissionsToUseToolInner()` 首先讀取 `context.abortController.signal.aborted`。已取消就丟 `AbortError`，不再碰規則或工具。

### 2. Whole-tool deny

`getDenyRuleForTool()` 只匹配沒有 `ruleContent` 的規則，例如 `Bash`，而不是 `Bash(npm publish:*)`。一旦匹配立即回 `deny`，reason 保存完整 rule provenance。

### 3. Whole-tool ask 與 sandbox 例外

`getAskRuleForTool()` 同樣只處理 whole-tool 規則。通常立即回 `ask`。唯一明示例外要求同時成立：

- 工具是 Bash；
- sandboxing 已啟用；
- `autoAllowBashIfSandboxed` 已啟用；
- `shouldUseSandbox(input)` 判定本次命令會進 sandbox。

此時不直接 allow，而是繼續到 Bash `checkPermissions()`，讓 command-specific rules 決定。若命令因 excluded command 或 `dangerouslyDisableSandbox` 不會被 sandbox，whole-tool ask 仍生效。

### 4. Schema parse 與 `Tool.checkPermissions()`

Runtime 先用工具的 Zod schema parse input，再呼叫 `tool.checkPermissions(parsedInput, context)`。Abort 類錯誤重新丟出；其他例外只記錄，保留預設 `passthrough`，最後通常成為 `ask`。這是 fail-to-prompt，而不是 permission-check exception 直接放行。

### 5. Tool result 中仍不可繞過的 early returns

依序是：

1. Tool 回 `deny`。
2. `requiresUserInteraction()` 的工具回 `ask`。
3. Tool 回的是 explicit content-level ask rule。
4. Tool 回的是 `safetyCheck` ask。

這些都發生在 bypass 與 whole-tool allow 之前。因此 bypass 的語意是跳過後段一般確認，不是刪除所有檢查。

### 6. Mode bypass、whole-tool allow、passthrough

通過前述阻擋後：

- `bypassPermissions` 直接 allow。
- `plan` 且 session 具有 `isBypassPermissionsModeAvailable` 也走 bypass allow。
- 否則再檢查 whole-tool allow rule。
- 最後把 `passthrough` 轉為 `ask`；tool 已回一般 `allow` 或 `ask` 則保留。

## 通用權限層與 Tool.checkPermissions 如何分工

通用層知道的是所有工具共有的 policy：

- whole-tool deny/ask/allow；
- bypass 與 outer mode transformation；
- prompt availability；
- auto classifier 與 denial tracking；
- abort 和最終 `PermissionDecision`。

`Tool.checkPermissions()` 知道的是 input 語意。例如 filesystem permission 會先檢查 deny、安全路徑與 content ask，再判斷 `acceptEdits` 是否可在允許工作目錄內放行寫入，接著找 allow rule，否則回 ask 與 `PermissionUpdate` suggestions。Bash/PowerShell 則解析命令與子命令，可能以 `subcommandResults` 保存每段原因。

這也解釋 whole-tool 與 content-level 規則為何分兩層：

- `Bash` 可在通用層直接匹配。
- `Bash(npm publish:*)` 必須由 Bash 理解 command 才能匹配。
- `Edit(/path/**)` 必須由 filesystem/path permission 解析實際路徑、symlink 與 working directories。

`checkRuleBasedPermissions()` 是供 hook allow 使用的受限版本。它重跑 whole-tool deny/ask、tool-level deny、content ask 與 safety ask，但刻意不執行 auto、`dontAsk`、async-agent transformation、bypass 或 whole-tool allow；caller 也必須先處理 `requiresUserInteraction()`。因此 hook allow 能略過普通 prompt，卻不能越過設定中的 deny/ask 與安全檢查。

## permission modes 如何改變 ask

下表的母體是「會碰到 mode-sensitive logic 的 tool use」，不只限於 unmatched action。這包含兩個時點：工具可在 `checkPermissions()` 內讀取 mode；通用層也可在 inner 的 bypass branch 或 outer 的 ask transformation 使用 mode。Whole-tool deny/ask、tool deny、forced-interaction ask、content ask 與 safety ask 等分支可能更早返回；表中的「更早返回」欄明確列出它們是否會越過後續 mode handling。

| mode | mode-sensitive handling | 更早返回、優先於後續 mode handling 的結果 | unresolved `ask` 與 user UI | important state changes |
|---|---|---|---|---|
| `default` | 沒有全域 fast path；工具回 `passthrough` 時，inner 轉成 `ask`。工具若已回 allow/deny，保留該結果 | whole-tool deny/ask、tool deny、forced-interaction/content/safety ask 都按原結果返回 | 互動 session 預期顯示；`shouldAvoidPermissionPrompts` context 先跑 hook，無決策則 deny | 使用者批准可套用 session 或 persistent `PermissionUpdate` |
| `plan` | 若 `isBypassPermissionsModeAvailable`，通過前置檢查的 action 在 inner allow；若 plan 的 auto state active，inner ask 在 outer 走 auto；其餘與 default 相同 | bypass branch 之前的 whole-tool deny/ask、tool deny、forced-interaction/content/safety ask 先從 inner 返回；plan-auto 只會在 outer 接手這些 ask，其中 forced interaction 與部分 safety ask 仍保持不可自動批准 | 普通 plan 可詢問；plan-auto 優先自動裁決，fallback 才 review | 保存 `prePlanMode`；可能切換 auto state、strip/restore dangerous rules |
| `acceptEdits` | 工具可在 `checkPermissions()` 對允許工作目錄內 edit/write 或受驗證的 shell edit 回 allow；其他 tool result 照 inner 規則成為 allow、deny 或 ask | whole-tool deny/ask 先於工具；tool deny、forced-interaction/content/safety ask 先於通用 allow rule | 未被工具自動接受的 ask 仍預期 UI；不可 prompt 時走 hook/deny | `setMode` 可來自批准；後續工具讀到新的 context mode |
| `auto` | Inner ask 到 outer 後，先試 acceptEdits fast path、safe-tool allowlist，再跑 classifier；一般 ask（包括 explicit content ask rule）可轉 allow、deny，或 fallback/review ask | whole-tool/tool deny 已是 hard deny，不進 auto；forced-interaction ask 與 non-classifier-approvable safety ask 不交給 classifier；其他 ask 可進 auto | 正常不先打擾；PowerShell gate、classifier context 過長、fail-open、denial limit 等可保留或產生 review ask；不可 prompt 分支可 deny/abort | strip dangerous allow rules；成功 `recordSuccess()`，block `recordDenial()` 並使用 denial limits |
| `bypassPermissions` | Action 只有通過所有 inner 前置分支，才在 bypass branch 直接 allow；不會再靠 unmatched-action prompt 決定 | whole-tool deny；whole-tool ask（sandbox auto-allow 例外除外）；tool deny、forced-interaction ask、explicit content ask、safety ask 都在 bypass 前返回 | bypass branch 本身不需要 UI；前置 ask 若存活，仍由正常互動/headless 邊界處理 | 不刪規則；allow reason 記為 mode，並保留 `updatedInput` |
| `dontAsk` | Inner allow/deny 保留；任何到達 outer 的 inner ask 都轉成 mode deny | 更早的 deny 保持 deny；更早的 ask 不算最終 blocker，因為 outer 會統一轉 deny | 不顯示批准 UI | 不新增 deny rule；final reason 為 `mode: dontAsk` |

### 原始碼摘錄 2：outer transformation

```ts
// abridged from hasPermissionsToUseTool()
if (result.behavior === 'ask') {
  const appState = context.getAppState()
  if (appState.toolPermissionContext.mode === 'dontAsk') {
    return { behavior: 'deny', /* mode reason */ }
  }
  if (
    appState.toolPermissionContext.mode === 'auto' ||
    (appState.toolPermissionContext.mode === 'plan' &&
      (autoModeStateModule?.isAutoModeActive() ?? false))
  ) {
    // classifier path
  }
}
```

它讀取 inner `result` 與最新 app state；`dontAsk` 選擇 deterministic deny，auto 選擇 classifier pipeline，最後才處理不可 prompt 的 context。產物仍是 `PermissionDecision`。順序讓 auto 在 headless context 仍有機會自動裁決，而不是因為沒有 UI 就提前 deny。

### Auto 的 fallback 並非單一 fail-open/fail-closed

Auto 對 ask 依序處理：

1. 不可交給 classifier 的 safety check：可 prompt 就保留 ask，不可 prompt 就 deny。
2. 需要使用者互動的 tool：保留 ask。
3. PowerShell auto gate 未開：可互動時保留 ask，不可互動時 deny。
4. 模擬 `acceptEdits` mode 再跑一次 tool `checkPermissions()`；若 allow，直接 allow。
5. Safe-tool allowlist：直接 allow。
6. Classifier：
   - allow：回 allow、`recordSuccess()`。
   - block：`recordDenial()`，通常回 deny。
   - transcript 過長：互動時 fallback ask；headless 因條件永久不會改善而 abort。
   - unavailable：`tengu_iron_gate_closed` 開啟時 fail-closed deny；關閉時回原 ask。
   - denial limit：互動時回 ask 讓使用者 review；headless abort。

### 原始碼摘錄 3：denial bookkeeping

```ts
// abridged from hasPermissionsToUseTool()
const newDenialState = recordDenial(denialState)
persistDenialState(context, newDenialState)
const denialLimitResult = handleDenialLimitExceeded(
  newDenialState,
  appState,
  classifierResult.reason,
  /* remaining arguments */
)
if (denialLimitResult) {
  return denialLimitResult
}
return { behavior: 'deny', /* classifier reason */ }
```

它讀取目前 denial state 與 classifier block，先增加連續/累計計數並寫回，再決定是正常 deny、fallback ask 或 headless abort。若先檢查 limit 才記錄，第三次連續拒絕不會在正確時點觸發 review，因此這個順序具有行為意義。

## 使用者批准或拒絕後，狀態如何更新

`useCanUseTool()` 收到 inner/outer 的 `ask` 後，可能先讓 coordinator、swarm worker 或 speculative Bash classifier 處理；仍未決定才交給 `handleInteractivePermission()`。

使用者批准時：

1. UI 提供可能修改過的 `updatedInput` 與零到多個 `PermissionUpdate`。
2. `handleUserAllow()` 先 `persistPermissions()`。
3. 可持久化 destination 寫入 settings；全部 updates 同時套用到最新 `ToolPermissionContext`。
4. 記錄 user accept，以及是否包含 persistent update。
5. 用 `inputsEquivalent()` 判斷 `userModified`，回 `allow`。

「只允許這一次」可傳空 updates，因此只回 allow，不改規則。「總是允許」不是特殊 behavior，而是 UI 提交一組 `addRules`、`setMode` 或 `addDirectories` updates；是否永久取決於 destination。

### 原始碼摘錄 4：批准與設定更新

```ts
// abridged from createPermissionContext()
persistPermissionUpdates(updates)
const appState = toolUseContext.getAppState()
setToolPermissionContext(
  applyPermissionUpdates(appState.toolPermissionContext, updates),
)
return updates.some(update => supportsPersistence(update.destination))
```

它讀取 UI/hook 選定的 updates 與最新 context；先寫可持久化 settings，再產生新的 in-memory context，最後回報此次批准是否包含 permanent destination。使用最新 context 而不是 prompt 出現時的舊快照，可避免等待期間的 mode/rule 更新被覆蓋。

使用者拒絕時，interactive handler 記錄 `user_reject`，再呼叫 `cancelAndAbort()`。這個 helper 在本地回傳的是帶拒絕訊息的 `ask`-shaped cancellation decision，而不是新增一條 deny rule；主 agent 無 feedback 的單純拒絕或明確 abort 也會觸發 `abortController.abort()`。Bridge 回應對外則送 `behavior: deny`。這個差異是 adapter contract，不應把 UI rejection 誤寫成 permission context 中的永久 deny。

Hook 批准走相似流程：可附 `updatedPermissions`，由 `handleHookAllow()` persist/apply，reason 標記為 `hook`。Hook 拒絕可設定 `interrupt`，此時會 abort 整個 controller。

## Hooks、headless 與 subagent 邊界

### PreToolUse hook

`toolHooks.ts` 將 hook 的 `permissionBehavior` 轉成 `PermissionResult`：

- `allow` 可帶 `updatedInput`。
- `ask` 可帶自訂 message 與 `updatedInput`。
- `deny` 忽略 `updatedInput`。
- 沒有 permission behavior、只有 `updatedInput` 時，修改輸入後繼續正常 permission flow。

`resolveHookPermissionDecision()` 不信任 hook allow 為最高權限：

- `requiresUserInteraction` 未由 hook 的 `updatedInput` 滿足，或 context 強制 `requireCanUseTool`：回到完整 `canUseTool()`。
- 其他 allow：呼叫 `checkRuleBasedPermissions()`；deny 規則可覆蓋 hook，ask 規則仍要求 prompt。
- Hook ask 透過 `forceDecision` 交給 `canUseTool()`，保留 hook message。

### PermissionRequest hook

當 outer result 是 ask 且 `shouldAvoidPermissionPrompts` 為 true，runtime 先執行 `PermissionRequest` hooks。Hook 可 allow、deny、修改 input 或更新 permissions；只有所有 hook 都沒有決策時，才回 `asyncAgent` deny。Hook 執行失敗會記錄錯誤並落到 auto-deny，而不是讓 agent 靜默執行。

### Headless / print

`src/cli/print.ts` 沒有 React permission dialog，而是建立不同 `CanUseToolFn`：

- SDK URL 強制使用 `stdio` permission prompting，交由 SDK consumer。
- `permissionPromptToolName === stdio` 使用 `StructuredIO.createCanUseTool()`。
- 指定 MCP permission prompt tool 時，先跑核心 permission decision；只有 ask 才呼叫該工具，並與 abort signal 競速。
- 未指定 prompt tool 時，adapter 直接回核心 `hasPermissionsToUseTool()` 的結果，不自行創造 UI。

所以「headless」不等於一定 deny；它可能把 ask 委派給 stdio/SDK/MCP。真正不能 prompt 的 background context 以 `shouldAvoidPermissionPrompts` 表示，並在 outer layer 走 hook-then-deny。

### Subagent

`runAgent.ts` 可用 agent definition 覆蓋 permission mode，但 parent 若是 `bypassPermissions`、`acceptEdits` 或 auto，這些 mode 有明確的繼承優先規則。Async agent 預設設 `shouldAvoidPermissionPrompts: true`；`bubble` 或明確宣告可顯示 prompt 的 background agent，則可設 `awaitAutomatedChecksBeforeDialog`，先等待自動檢查，再把 unresolved ask 冒泡給可互動邊界。

Agent 的 `allowedTools` 會替換 parent 的 session allow rules，但保留 `cliArg` allow rules。Auto denial tracking 在 async subagent 可使用 `localDenialTracking`，因為其 `setAppState` 可能是 no-op。

## Abort 與失敗如何傳播

Abort 的檢查點不只一個：

1. Inner function 開始前。
2. `Tool.checkPermissions()` 丟出 `AbortError` / `APIUserAbortError` 時重新傳播。
3. Auto classifier 接收同一個 signal。
4. `useCanUseTool()` 在建立 context 後、allow 前、取得 description 後、顯示 UI 前重複 `resolveIfAborted()`。
5. `PermissionRequest` hooks 接收 signal。
6. Headless custom permission tool 與 signal `Promise.race()`。

`useCanUseTool()` catch 到 abort 類錯誤後會記錄 cancellation，再以 `cancelAndAbort()` resolve；非 abort 例外也會記錄並走 cancellation，而不是執行工具。

幾個失敗分支值得分開：

- Tool schema parse 或 `checkPermissions()` 的一般例外：記錄後保留 `passthrough`，通常成為 ask。
- PermissionRequest hook 失敗：在不可 prompt context 中 fall through 到 deny。
- Auto classifier unavailable：依 iron-gate 動態設定 deny 或保留 ask。
- Auto classifier transcript 過長：互動時保留 ask，headless abort。
- 等待 permission prompt 時 abort：自訂 prompt adapter 回帶 `permissionPromptTool` reason 的 deny；React path 走 cancellation helper。

## 走一遍具體案例

### 案例一：whole-tool deny

**輸入 / 初始狀態**

```text
tool = Bash
input = { command: "git status" }
mode = bypassPermissions
alwaysDenyRules.policySettings = ["Bash"]
abort = false
```

**決策順序**

1. Abort 未觸發。
2. `getDenyRuleForTool()` 命中 policy 的 whole-tool `Bash`。
3. 立即回 deny；不執行 whole-tool ask、Bash `checkPermissions()`、bypass 或 allow rule。

**狀態變化**：無 permission update；無 denial tracking 變化。

**最終結果**：`deny`，reason 是帶 `source: policySettings` 的 rule。

**為什麼**：whole-tool deny 位於 bypass 前。這直接證明 bypass 不是刪除所有檢查。

### 案例二：tool-specific ask，使用者只批准一次

**輸入 / 初始狀態**

```text
tool = Edit
input = { file_path: "/repo/src/a.ts", ... }
mode = default
無匹配 whole-tool deny / ask / allow
filesystem check 無 content allow，路徑沒有 safety violation
abort = false
```

**決策順序**

1. 通用 whole-tool deny/ask 都不匹配。
2. Edit 的 `checkPermissions()` 進入 filesystem write permission。
3. 不符合 `acceptEdits`，也沒有 content allow，回 `ask`，並可附 `setMode: acceptEdits` 等 suggestions。
4. Inner 保留 tool-specific ask；outer default 不轉換。
5. `useCanUseTool()` 顯示互動 prompt。
6. 使用者選「只允許這一次」，傳回原 input、空 `PermissionUpdate[]`。
7. `handleUserAllow()` 不寫 settings、不改 context，記錄 user accept，回 allow。

**狀態變化**：permission rules 與 mode 不變；只有 decision logging。

**最終結果**：`allow`，僅這次 tool use 可執行。

**為什麼**：ask 是待決狀態，不是 deny。批准由互動層把它解成 allow；若使用者選 persistent option，同一流程會先 apply/persist updates 再 allow。

### 案例三：ask 在 `dontAsk` 下轉成 deny

**輸入 / 初始狀態**

```text
tool = Bash
input = { command: "npm test" }
mode = dontAsk
無匹配規則
Bash checkPermissions = passthrough
abort = false
```

**決策順序**

1. Inner 通過 deny/ask、tool deny、安全與 allow 檢查。
2. `passthrough` 被 inner 轉成 `ask`。
3. 回到 outer `hasPermissionsToUseTool()`。
4. Outer 看到 mode 是 `dontAsk`，把 ask 轉成 deny。
5. 不進 UI，也不進 auto classifier。

**狀態變化**：無新增 deny rule；context mode 保持 `dontAsk`。

**最終結果**：`deny`，reason 是 `{ type: "mode", mode: "dontAsk" }`。

**為什麼**：`dontAsk` 是 outer transformation。若把它錯放進 inner，便無法準確表達「先得到 ask，再禁止詢問」的語意。

### 案例四：auto classifier block，第三次連續拒絕回人工 review

**輸入 / 初始狀態**

```text
inner result = ask
mode = auto
不符合 acceptEdits fast path，也不在 safe-tool allowlist
denialTracking = { consecutiveDenials: 2, totalDenials: 7 }
classifier = block("dangerous action")
interactive context
```

**決策順序**

1. Outer 進 auto path，classifier 回 block。
2. `recordDenial()` 得到 `{ consecutiveDenials: 3, totalDenials: 8 }` 並持久化。
3. `shouldFallbackToPrompting()` 命中連續拒絕上限。
4. `handleDenialLimitExceeded()` 回帶 classifier reason 的 ask，讓使用者 review。

**狀態變化**：拒絕計數已增加；連續計數不在此分支自動清零。

**最終結果**：`ask`，不是第三個 classifier deny。若同樣情況在 `shouldAvoidPermissionPrompts` context，結果是 `AbortError`。

**為什麼**：denial tracking 是 auto 的 circuit breaker，避免 agent 在無人工檢視下連續重試被 classifier 阻擋的動作。

## 證據、限制與設計取捨

- Control flow 由 CodeGraph 的 `useCanUseTool → hasPermissionsToUseTool → hasPermissionsToUseToolInner` call relation，以及各 symbol source 重建；early return 順序以 function body 為準。
- Whole-tool rule、content rule 與 hook allow 的邊界由 `checkRuleBasedPermissions()` 與 `resolveHookPermissionDecision()` 互相驗證。
- Mode 表以通用 inner/outer flow 加上 filesystem、Bash/PowerShell mode-specific checks 核對；因此 `acceptEdits` 被描述為工具可選擇 allow 的能力，而不是全域 unconditional allow。
- **推論**：將 denial limit 稱為 circuit breaker 是對其行為目的的工程描述；原始型別只定義計數與 fallback，並未把該型別命名為 circuit breaker。
- **版本限制**：`auto`、classifier fast paths、部分 PowerShell 與 dangerous-rule cleanup 受 feature/build gates 控制。
- **尚未確認**：不同產品通道對 `tengu_iron_gate_closed` 的即時設定值；source 只證明 gate 開關時各自的 fail-closed / fail-open 分支。
- OS sandbox 的強度不能由 `canSandboxAutoAllow` 推導。本文只證明 permission layer 在特定 Bash 條件下略過 whole-tool ask，後續 containment 保證必須另讀 sandbox 實作。

設計上的主要取捨是增加分層複雜度，換取三件事：tool 能保留 domain-specific 判斷；管理規則與 safety check 不會被寬鬆 mode 輕易蓋過；互動式、headless、hook 與 subagent 可以共享同一個核心 decision，而在最外層採用不同 resolution adapter。

## 源碼入口

- `src/Tool.ts`
  - `Tool`
  - `Tool.checkPermissions`
  - `ToolPermissionContext`
  - `ToolUseContext`
- `src/types/permissions.ts`
  - `PermissionMode`
  - `PermissionRule`
  - `PermissionResult`
  - `PermissionDecision`
  - `PermissionUpdate`
- `src/utils/permissions/permissionSetup.ts`
  - `initializeToolPermissionContext`
  - `transitionPermissionMode`
  - `stripDangerousPermissionsForAutoMode`
  - `restoreDangerousPermissions`
  - `prepareContextForPlanMode`
- `src/utils/permissions/permissions.ts`
  - `hasPermissionsToUseTool`
  - `hasPermissionsToUseToolInner`
  - `checkRuleBasedPermissions`
  - `getDenyRuleForTool`
  - `getAskRuleForTool`
  - `toolAlwaysAllowedRule`
  - `persistDenialState`
  - `handleDenialLimitExceeded`
- `src/utils/permissions/PermissionResult.ts`
  - permission result re-exports 與 `getRuleBehaviorDescription`
- `src/utils/permissions/PermissionRule.ts`
  - rule schema 與 content rule contract
- `src/utils/permissions/PermissionUpdate.ts`
  - `applyPermissionUpdate`
  - `applyPermissionUpdates`
  - `persistPermissionUpdates`
  - `supportsPersistence`
- `src/utils/permissions/PermissionUpdateSchema.ts`
  - update/destination schema
- `src/utils/permissions/denialTracking.ts`
  - `DenialTrackingState`
  - `recordDenial`
  - `recordSuccess`
  - `shouldFallbackToPrompting`
- `src/utils/permissions/filesystem.ts`
  - content-level path deny/ask/allow、`acceptEdits` 與 suggestions
- `src/hooks/useCanUseTool.tsx`
  - interactive decision entry 與 allow/deny/ask routing
- `src/hooks/toolPermission/PermissionContext.ts`
  - `createPermissionContext`
  - `persistPermissions`
  - `handleUserAllow`
  - `handleHookAllow`
  - abort/cancellation helpers
- `src/hooks/toolPermission/handlers/interactiveHandler.ts`
  - user allow/reject/abort resolution
- `src/cli/print.ts`
  - `createCanUseToolWithPermissionPrompt`
  - `getCanUseToolFn`
- `src/services/tools/toolHooks.ts`
  - `resolveHookPermissionDecision`
  - PreToolUse hook result mapping
- `src/tools/AgentTool/runAgent.ts`
  - subagent mode inheritance
  - `shouldAvoidPermissionPrompts`
  - `awaitAutomatedChecksBeforeDialog`
