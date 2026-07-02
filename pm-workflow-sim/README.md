# PM 工作流全模擬:一個功能的完整生命週期

一個虛構但寫實的需求——「10 人團隊值班換班工具」——從**訪談挖需求**到**上線覆盤**走完正規公司的完整流程,
每個階段附真實公司會產出的工件。目的:直觀看懂「產品經理把一個功能設計完整」到底做了哪些事。

## 走讀順序(按編號讀,別跳)

| # | 階段 | 本目錄檔案 | 真實公司裡的載體 | 核心工件 |
|---|---|---|---|---|
| 0 | 需求發現 | [00-discovery.md](00-discovery.md) | 訪談 + FigJam affinity | 訪談指南、逐字稿、洞察合成 |
| 0b | Kickoff | [00b-kickoff-minutes.md](00b-kickoff-minutes.md) | 30min 會議 + Notion | 會議紀要(決議/OQ/AI) |
| 1 | 立項說服 | [01-one-pager.md](01-one-pager.md) | Notion | 1-pager |
| 2 | 腦暴收斂 | [02-figjam-brainstorm.md](02-figjam-brainstorm.md) | **FigJam** | journey、方案發散、user flow |
| 3 | 定義 | [03-prd-draft.md](03-prd-draft.md) | Notion/Confluence | PRD v1 + 完整性三表(留「?」) |
| 4 | 互動設計 | [04-wireframes/index.html](04-wireframes/index.html) | **Figma** | 低保真線框 ×5 屏,可點擊 |
| 5 | 雙評審 | [05-review-comments.md](05-review-comments.md) | **Figma comments** | 評審串 ×7 + PRD delta |
| 6 | 用戶驗證 | [06-usability-test.md](06-usability-test.md) | 原型 + 真人 | 測試腳本、記錄、修改決策 |
| 7 | 定稿交付 | [07-final-prd.md](07-final-prd.md) | Notion + Jira/Linear | PRD Final + 拆票 ×7 |
| 8 | 覆盤 | [08-retro.md](08-retro.md) | Notion | 指標對賬 + 流程覆盤 |
| 9 | 現場能力 | [09-live-skills.md](09-live-skills.md) | 真人回合 | 訪談難場面話術、範圍談判、接案商業層、mock 模板 |

線框直接瀏覽器打開:`open pm-workflow-sim/04-wireframes/index.html`,藍色按鈕可點,模擬 Figma 原型模式。

## 這套流程的三根柱子(看完全部後回來驗證)

1. **完整性靠三張表,不靠靈感**:畫面×七態、操作×五問、實體×角色 CRUD。v1 誠實留「?」,
   評審對著「?」轟——05 的 7 條 comment 有 5 條由表格空格引出。表格是評審武器,不是作業。
2. **PRD 是唯一事實源**:訪談、腦暴、comment、測試的所有結論最後都回寫 PRD。
   追溯鏈:07 的每條規則 ← 05/06 的某條結論 ← 00 的某句訪談。斷鏈 = 半年後沒人知道為什麼。
3. **解法會騙人,問題不會**:小李要「App」,真問題是「協議和改表脫節」(00 訪談 A);
   覆盤時 App 沒人再提(08 停車場)。訪談問過去的事實,不問未來的假設。

## 遷移到真工具(練肌肉的作業)

流程你已看懂,工具操作要自己長繭:

1. **FigJam**:把 02 重畫成真畫板——便利貼、連線,45 分鐘
2. **Figma**:把 04 的 S1-S4 用社群 lo-fi wireframe kit 重畫,prototype 模式連上熱區
3. **Figma comments**:自己隔天換帽子,把 05 的 C2、C5 用真 comment 釘在畫面上練 resolve
4. **Notion**:建「產品 Hub」,把 01→03→07 放成一頁的版本歷史,狀態 Draft → In Review → Final

之後做自己的產品,套同一條管線,產物一比一對照本目錄。
