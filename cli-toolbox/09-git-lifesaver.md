# 09 · git 救命級進階

> 不是 `add/commit/push` 那些。是**闖禍了怎麼救、bug 是哪個提交引入的、歷史怎麼整理**——資深工程師跟初級拉開差距的地方。

---

## 收口地圖(一個原語,讓你敢用)

**原語:git 幾乎不真的刪東西。** 你的提交即使被 `reset`/`rebase` 甩掉,物件還躺在倉庫裡、`reflog` 還記著(預設約 90 天)。

→ 推論:**幾乎所有「闖禍」都能救**。理解這條,你才敢用 `reset --hard`、`rebase` 這些「看起來危險」的命令。

五個救命場景:

| 場景 | 工具 |
|---|---|
| 救回誤刪/誤操作 | `reflog`(後悔藥) |
| 找出哪個提交弄壞的 | `bisect`(二分) |
| 找「誰改了這行/這個字串」 | `blame` / `log -S` |
| 整理歷史 | `rebase -i` |
| 臨時收起 / 搬運提交 | `stash` / `cherry-pick` / `revert` |

---

## 1. `reflog` —— 後悔藥(最該先學)

`reflog` 記錄 HEAD 的每一次移動。誤操作後,先 `reflog` 找到「闖禍前」那個狀態,再跳回去。

| 命令 | 作用 |
|---|---|
| `git reflog` | 看 HEAD 移動歷史(每行一個 `HEAD@{n}`) |
| `git reset --hard HEAD@{2}` | **回到 2 步之前**的狀態 |
| `git branch recover HEAD@{1}` | 把某個歷史點重建成分支 |

> 能救的災:**誤 `reset --hard`、誤 `rebase`、誤刪分支、誤 `checkout` 丟改動**——全都 `reflog` 找回。記住:**慌之前先 `git reflog`。**

---

## 2. `bisect` —— 二分揪出「哪個提交引入 bug」

| 命令 | 作用 |
|---|---|
| `git bisect start` | 開始 |
| `git bisect bad` | 標記「當前是壞的」 |
| `git bisect good v1.2` | 標記「這個老版本是好的」 |
| (git 自動 checkout 中間提交,你測,標 `good`/`bad`) | 二分逼近 |
| `git bisect run ./test.sh` | **全自動**:腳本回 0=good 非0=bad |
| `git bisect reset` | 結束,回到原處 |

> 幾百個提交裡找出哪個引入了 bug,`bisect` 把它變成 `log2(n)` 次測試。配 `run` + 一個復現腳本,**全自動定位**,這是面試和實戰都亮眼的一招。

---

## 3. 找「誰/哪個提交動了這個」

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `git blame file` | 每行**最後**由誰、哪個提交改的 | 追責 / 找上下文 |
| `git log -S '字串'` | **pickaxe**:哪個提交**引入或刪除**了這個字串 | 找「這段邏輯/這個 bug 從哪來」的神器 |
| `git log -p -- file` | 某檔案的**完整變更歷史**(帶 diff) | — |
| `git log -L :funcName:file` | 某**函數**的演變史 | 看一個函數怎麼變成今天這樣 |

> `git log -S 'someBuggyCall'` 比 `blame` 更強:blame 只看「最後一次改」,`-S` 能挖到「**最早引入**」這行的那個提交。

---

## 4. `rebase -i` —— 整理歷史

| 命令 | 作用 |
|---|---|
| `git rebase -i HEAD~3` | 改最近 3 個提交:`squash`合併 / `reword`改訊息 / `drop`刪 / 調順序 |
| `git commit --amend` | 改**最後一次**提交(訊息或補檔案) |
| `git rebase --abort` | 中途後悔,全部還原 |

> ⚠️ **黃金規則:別改「已推送到共享分支」的歷史。** 自己的本地/feature 分支隨便整理;一旦 push 且別人可能基於它工作,改歷史會害慘隊友。真要推改過的,用 `git push --force-with-lease`(比 `--force` 安全:別人有新提交時會拒絕)。

---

## 5. `stash` / `cherry-pick` / `revert`

| 命令 | 作用 |
|---|---|
| `git stash` / `git stash pop` | 臨時收起未提交改動 / 取回 |
| `git stash -u` | 連**未追蹤**檔案一起收 |
| `git cherry-pick <sha>` | 把**某一個提交**搬到當前分支 |
| `git revert <sha>` | **安全地反做**一個提交(產生反向提交,**不改歷史**) |

> `revert` vs `reset` 的關鍵:**撤銷一個「已推送」的提交,用 `revert`**(新增一個反向提交,歷史完整、隊友安全);`reset` 會改寫歷史,只適合本地還沒 push 的。

---

## 救命場景速查(「我闖禍了」→ 怎麼救)

| 我闖禍了 | 救法 |
|---|---|
| 誤 `reset --hard` 丟了提交 | `git reflog` → `git reset --hard HEAD@{n}` |
| 誤刪了分支 | `git reflog` 找 SHA → `git branch 名 <sha>` |
| 提交到了錯的分支 | 在對的分支 `cherry-pick`,原分支 `reset` 掉 |
| commit message 寫錯(**沒 push**) | `git commit --amend` |
| 想撤一個**已 push** 的提交 | `git revert <sha>`(別 `reset` 改歷史) |
| 改到一半要緊急切分支 | `git stash` → 切 → 回來 `git stash pop` |
| bug 是哪個提交引入的 | `git bisect` / `git log -S` |
| 想看某行為什麼長這樣 | `git blame` → `git show <sha>` |

---

## 看狀態/差異(順手)

```bash
git status -sb                      # 精簡狀態 + 分支追蹤
git diff           / --staged       # 工作區 / 暫存區 的改動
git diff main...feature             # feature 自分叉以來的改動
git log --oneline --graph --all     # 可視化分支拓撲
git show <sha>                      # 看某個提交的完整內容
```

---

## 深挖

- 團隊 git 工作流、提交規範、分支策略 → **`engineering-handbook`**(規範層)
- 外部權威:*Pro Git*(免費,git-scm.com/book)第 7、10 章把 reflog / 物件模型講透
