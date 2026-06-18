# Claude Code Permission / Sandbox Deep Dive 設計

## 背景

`ai/claude-code-source/` 現有筆記以面試複盤和高層心智模型為主。它們能說明 Claude Code 有哪些 runtime 元件，卻不足以回答：

- 一個具體輸入經過哪些函式與判斷；
- 每一步讀取、建立或修改了什麼狀態；
- 多條規則衝突時誰優先；
- permission、Bash 安全分析與 sandbox 各自在哪一層生效；
- macOS、Linux 如何實際限制檔案與網路能力；
- 初始化、取消、設定更新及失敗回退如何處理；
- 哪些結論由原始碼或測試確認，哪些只是推論。

因此需要在保留概覽層的同時，增加按「機制」拆分的 implementation deep dive。第一批以 Permission / Sandbox 作為標竿，先確認理想深度、敘事方式與驗證標準，再把相同方法擴展到其他章節。

原始碼只讀參考：

```text
/Users/buoy/Development/gitrepo/Claude-Code-true
```

筆記輸出位置：

```text
/Users/buoy/Development/gitrepo/interview/ai/claude-code-source
```

## 目標

完成後，讀者即使暫時不打開原始碼，也能：

1. 沿執行順序解釋一個 Bash `tool_use` 如何得到 allow、ask 或 deny。
2. 區分 permission、Bash command analysis 與 sandbox containment 的責任。
3. 解釋 shell command 如何解析、拆分及匹配規則。
4. 解釋 sandbox 如何初始化、取得設定、包裝命令並限制檔案與網路。
5. 預測典型正常、拒絕、繞過、失敗及取消案例的結果。
6. 知道需要繼續查證時應從哪個檔案和 symbol 開始閱讀。

## 非目標

- 不逐行翻譯整個 Claude Code 原始碼。
- 不把文件做成以行號為中心的索引；行號容易隨版本漂移。
- 不大量貼出原始碼後把理解工作留給讀者。
- 不在第一批重寫 `00` 到 `14` 的所有章節。
- 不改動 `/Users/buoy/Development/gitrepo/Claude-Code-true`。
- 不把 `excludedCommands`、prompt 或模型自身判斷誤寫成安全邊界。

## 整體結構

採用「概覽導讀 + 機制級 Deep Dive + 端到端案例」的混合結構：

```text
ai/claude-code-source/
├── 06-permission-and-sandbox.md
└── deep-dives/
    ├── 06a-permission-decision.md
    ├── 06b-bash-security-analysis.md
    ├── 06c-sandbox-runtime.md
    └── 06d-end-to-end-scenarios.md
```

### 概覽章的責任

`06-permission-and-sandbox.md` 保留為導讀，不承擔全部實作細節。它只需要：

- 建立 permission 與 sandbox 的責任分界；
- 展示一條簡化的完整執行鏈；
- 解釋四篇 Deep Dive 的關係；
- 告訴讀者面對不同問題應閱讀哪一篇；
- 保留適合快速複習的總結與面試表達。

### Deep Dive 的責任

每篇只追一組高度相關的機制，避免把所有內容重新壓進另一篇巨型文件：

- `06a` 回答「為何這個動作被允許、詢問或拒絕」。
- `06b` 回答「Bash command 如何被理解及匹配安全規則」。
- `06c` 回答「被允許的命令如何受到系統能力限制」。
- `06d` 用真實案例重新串起前三篇的機制。

## 每篇 Deep Dive 的固定模板

每篇依下列順序組織：

1. **具體問題**：這項機制防止或處理什麼實際問題。
2. **完整流程**：先用流程圖或偽代碼建立全貌。
3. **輸入、輸出與狀態**：列出關鍵資料結構及其責任。
4. **按執行順序拆解**：從入口一路追到結果，不按檔案名稱堆砌資訊。
5. **關鍵分支與優先順序**：明確說明衝突規則和提前返回。
6. **必要的真實源碼**：短片段後立即解釋其作用。
7. **錯誤與邊界**：包含取消、併發、fallback、安全邊界和平台差異。
8. **具體案例**：展示輸入、逐步判斷、狀態變化與輸出。
9. **測試證據**：指出哪些測試或最小實驗驗證行為。
10. **設計取捨與限制**：解釋原因，標示尚未確認的部分。
11. **源碼入口**：只列重要檔案與 symbol，方便繼續閱讀。

模板是內容檢查表，不要求所有小節機械地使用完全相同的篇幅。每篇應以控制流的可理解性優先。

## `06a`：Permission Decision

### 核心問題

模型提出一個 `tool_use` 後，runtime 如何在產生副作用之前得到 allow、ask 或 deny。

### 必須涵蓋

- `ToolPermissionContext` 如何由 CLI、settings、policy、session 和工作目錄資訊組成。
- allow、ask、deny 規則有哪些來源，來源如何影響更新與持久化。
- 通用權限層和工具自身 `checkPermissions()` 的責任分界。
- `hasPermissionsToUseTool()` 與內層裁決的真實判斷順序。
- whole-tool 規則、內容級規則、安全檢查及強制互動的優先順序。
- default、plan、acceptEdits、auto、bypassPermissions、dontAsk 的行為差異。
- auto classifier、allowlist、denial tracking 及回退行為。
- 使用者批准、一次性批准、持久化批准及拒絕如何改變後續狀態。
- headless、async agent 或無法顯示 permission UI 時的行為。
- abort 在權限檢查階段如何傳播。

### 不在本篇展開

- shell command AST 與 Bash rule matching 的細節。
- sandbox 的平台級 containment 實作。

## `06b`：Bash Security Analysis

### 核心問題

Bash 是一個可間接執行大量副作用的通用入口。runtime 如何理解 command 的結構，避免只靠原始字串做脆弱判斷。

### 必須涵蓋

- Bash tool input 如何進入命令級權限檢查。
- compound command 如何拆成子命令。
- parser 的 simple、too-complex、parse-unavailable 結果如何影響後續裁決。
- exact、prefix、wildcard 規則如何解析和匹配。
- shell operator、控制字元、Unicode whitespace 與特殊 expansion 的處理。
- safe wrapper、env assignment stripping 的目的、固定點處理及停止條件。
- 為何某些環境變數可能改變 binary resolution，不能安全剝除。
- approval suggestion 如何產生，為何拒絕過寬 prefix。
- `Bash(*)`、shell wrapper、下載執行等危險規則如何識別和清理。
- `excludedCommands` 如何重用匹配機制，以及它為何只是便利功能而非安全邊界。
- command 無法可靠解析時的保守處理與失敗語義。

### 不在本篇展開

- permission mode 的完整狀態機。
- sandbox profile、檔案限制和網路代理的底層實作。

## `06c`：Sandbox Runtime

### 核心問題

一個已獲權限執行的 Bash command，如何被放進受限環境，並在不同平台限制檔案、網路與程序能力。

### 必須涵蓋

#### 啟用與政策

- sandbox settings 如何轉換成 runtime config。
- 平台支援、平台 allowlist、設定開關及依賴檢查如何共同決定 enablement。
- sandbox required policy、unsandboxed command policy 與 locked settings 的作用。
- `shouldUseSandbox()` 對全域狀態、空 command、override 和 excluded command 的判斷。

#### 初始化生命週期

- `SandboxManager` 與底層 manager 的適配關係。
- initialization promise 如何同步建立，避免命令在初始化狀態尚未記錄前搶先執行。
- worktree 主倉庫路徑為何在初始化時解析和快取。
- settings subscription 如何更新 runtime config。
- `refreshConfig()` 為何需要同步更新。
- 初始化失敗後如何清理狀態、記錄錯誤和允許重試。

#### 檔案系統限制

- 可讀、可寫及 deny 路徑如何從 defaults、cwd、額外目錄、settings 和 managed policy 組合。
- worktree、主倉庫及特殊 runtime 路徑如何處理。
- glob、路徑標準化與 Linux pattern warning 的限制。
- 命令嘗試存取禁止路徑時，OS-level failure 如何回到工具結果。

#### 網路限制

- domain allowlist、managed-only policy 和動態 ask callback 如何協作。
- HTTP proxy、SOCKS proxy、Linux socket path 的角色。
- Unix socket、本地 bind 及 loopback 相關設定。
- 網路初始化的等待點，以及命令過早啟動如何避免。
- 未允許 host 的阻擋、詢問和批准後刷新流程。

#### 平台實作

- macOS 與 Linux 使用的 containment 元件及命令包裝差異。
- 原始 command、shell 和 runtime config 如何轉換為最終 spawn command。
- nested sandbox、較弱模式或平台限制如何影響能力。
- 不支援平台或缺少依賴時，required 與 non-required policy 的不同結果。

#### 執行、取消與診斷

- `wrapWithSandbox()` 如何等待初始化並委派底層包裝。
- abort signal 如何到達 sandbox wrapper 和實際程序。
- violation store 或平台日誌如何收集拒絕資訊。
- stderr 如何被補充 sandbox failure 診斷。
- sandbox 啟用但初始化結果不可用時如何失敗。
- sandbox 不啟用時，permission 如何仍然獨立保護副作用。

## `06d`：End-to-End Scenarios

### 核心問題

把前三篇分散的機制放回一條實際執行鏈，讓讀者可以預測結果而不是只記住元件名稱。

### 最少案例集

1. 權限批准，命令正常進入 sandbox 並完成。
2. whole-tool deny 命中，sandbox 完全不執行。
3. 工具內容級檢查要求 ask，使用者拒絕。
4. 允許讀取工作區，但嘗試寫入工作區外被 OS containment 阻擋。
5. 網路 host 已在 allowlist，命令直接通過。
6. 網路 host 未知，callback 詢問後批准並刷新設定。
7. managed-only policy 阻止動態批准未知 host。
8. compound command 只有其中一段命中 `excludedCommands`。
9. `dangerouslyDisableSandbox` 被 policy 允許。
10. `dangerouslyDisableSandbox` 存在但 policy 不允許。
11. sandbox 依賴不可用且 policy 非 required。
12. sandbox 依賴不可用且 policy required。
13. 執行中的 sandbox command 被 abort。
14. settings 動態變更後，下一條 command 使用新限制。

每個案例使用統一格式：

```text
輸入
→ 初始狀態與設定
→ permission 判斷
→ Bash 分析
→ sandbox decision
→ process / OS 結果
→ tool_result
→ 為何得到此結果
```

如果某層不參與案例，必須明確寫「未進入此層」，而不是直接省略。

## 程式碼呈現策略

文件先講邏輯，再選擇表示方式。

### 偽代碼

適用於：

- 一條流程跨越多個檔案或函式；
- 原始實作含大量 telemetry、UI 或 feature flag 雜訊；
- 需要突出判斷順序和狀態變化。

偽代碼必須明確標記為偽代碼，不得偽裝成可直接編譯的真實來源。

### 真實源碼

適用於：

- 判斷順序本身就是行為契約；
- 關鍵資料結構難以只用文字準確表達；
- 某項安全技巧值得保留原貌；
- 平台 adapter 或 wrapper 的真實介面有助理解。

片段應短小，只保留理解當前論點所需的內容。若有刪節，使用明確省略標記；不得無聲修改後仍稱為原始碼。

### 流程圖

存在三個以上重要分支、多個責任層或明顯狀態轉換時使用。流程圖應突出決策所有者，例如 permission layer、Bash analyzer、sandbox adapter 或 OS。

### 表格

用於比較：

- permission modes；
- 規則來源和優先順序；
- macOS / Linux；
- required / optional sandbox；
- settings、policy 和輸入組合對結果的影響。

### 原始碼定位

檔案和 symbol 是查證入口，不是敘事主體。正文不強制標註精確行號；只有在確實有助於定位時才使用。

## 證據與可信度

每項重要實作結論至少由下列一種證據支持：

1. 原始碼實作與靜態呼叫關係；
2. 現有測試；
3. 可安全執行的最小實驗。

證據選擇原則：

- 控制流和資料結構主要依據原始碼。
- 邊界條件和行為契約優先尋找測試。
- 平台或環境相關行為若可安全重現，可增加最小實驗。

無法由上述方式確認的內容必須標為：

- **推論**：可由已知實作合理推出，但沒有直接證據；
- **尚未確認**：目前證據不足；
- **版本限制**：只適用於本次閱讀的原始碼版本。

不得只憑檔名、symbol 名稱或註解把行為寫成已確認事實。

## 錯誤與邊界的寫作要求

每篇不能只描述 happy path。至少要回答：

- 錯誤在哪一層產生；
- 是 throw、return decision、process exit，還是轉成 `tool_result`；
- 是否允許重試；
- 是否修改或保留 session/runtime 狀態；
- abort 是否可能留下未完成程序或不合法 transcript；
- fallback 是安全降級、功能降級，還是直接失敗；
- policy required 時是否禁止 fail-open。

安全相關內容必須區分：

- 安全邊界；
- 防呆或便利功能；
- 可觀測性與診斷；
- 模型提示或使用者體驗。

## 驗證方式

### 結構驗證

- 概覽章能連到四篇 Deep Dive。
- 四篇內容邊界沒有大段重複。
- 每個重要機制只在一篇中完整定義，其他篇使用連結引用。

### 內容驗證

- 每篇都有一條從輸入到輸出的完整流程。
- 每個主要提前返回與失敗分支都有說明。
- 真實源碼與偽代碼標示清楚。
- 每項平台差異均有原始碼、測試或明確的不確定性標籤。
- 所有案例都能指出每一步的決策層。

### 原始碼一致性驗證

- 使用 CodeGraph 追蹤 symbol、caller、callee 和跨檔控制流。
- 若 CodeGraph 顯示 pending sync，只重新讀取被標記為 stale 的檔案。
- 不以 grep 重複驗證 CodeGraph 已確認的結構關係。
- literal 設定名稱、錯誤字串和註解可使用文字搜尋補充。

### 最終可讀性驗證

讓讀者僅根據文件回答下列問題：

- 這條 command 為何是 allow、ask 或 deny？
- 哪一層決定是否進入 sandbox？
- 進入 sandbox 後，檔案和網路能力如何受到限制？
- 初始化或依賴失敗時會 fail-open 還是 fail-closed，原因是什麼？
- 使用者修改設定後，新設定何時開始生效？
- command 被取消時，signal 經過哪些元件？

若答案仍只能是元件名稱而不能描述判斷與狀態變化，該段不算完成。

## 實施順序

標竿章按以下順序撰寫：

1. 建立 `deep-dives/` 和四篇文件骨架。
2. 更新 `06-permission-and-sandbox.md` 成為導讀並加入導航。
3. 完成 `06a`，先固定權限裁決的語言和資料模型。
4. 完成 `06b`，補齊 Bash command analysis。
5. 完成 `06c`，深入 sandbox runtime 與平台 containment。
6. 完成 `06d`，用案例驗證前三篇是否真的能串起來。
7. 回頭消除重複、補連結並檢查術語一致性。
8. 以完成條件驗收標竿章，再決定其他章節的 Deep Dive 清單。

`06c` 依賴 `06a` 和 `06b` 已建立清楚的責任邊界；`06d` 必須最後撰寫，因為它同時也是前三篇的整合測試。

## 完成條件

Permission / Sandbox 標竿章只有同時滿足以下條件才算完成：

- 概覽與四篇 Deep Dive 均已完成並互相連結。
- permission、Bash analysis、sandbox containment 的責任沒有混用。
- 四篇均以控制流組織，而不是檔案清單。
- 關鍵邏輯包含足夠的偽代碼、短原始碼、圖表或案例。
- 至少十四個端到端案例均能逐層預測結果。
- 正常、拒絕、取消、初始化失敗、依賴缺失、動態設定和平台差異均有覆蓋。
- 已確認、推論與尚未確認內容清楚區分。
- 讀者能從源碼入口繼續追蹤，但不依賴行號才能理解正文。
- 沒有 `TODO`、`TBD` 或以「之後再補」代替的核心內容。

完成標竿章後，才能以此模板規劃其餘章節的 Deep Dive；不預先假設所有章節都需要相同數量的子篇。
