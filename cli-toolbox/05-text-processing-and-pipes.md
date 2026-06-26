# 05 · 文本三劍客與管道

> 從一坨日誌/輸出裡撈出你要的東西。資深工程師不靠寫腳本,靠**幾個小工具用 `|` 拼起來**,一行解決。

---

## 收口地圖(記這條主鏈,別背參數)

文本處理就三個動作 + 一種黏合劑:

| 動作 | 工具 | 一句話 |
|---|---|---|
| **篩選行** | `grep` | 留下/排除含某字串的行 |
| **取欄位 / 算** | `awk` | 把每行切成 `$1 $2…`,挑欄位、過濾、統計 |
| **改文字** | `sed` | 對流做替換、刪行、取區間 |
| **黏合** | `\|` `xargs` | 串起小工具;`xargs` 把「輸出」變「參數」(原語 3) |

> **90% 的日常需求 = 這條主鏈**:`grep 找 → awk 取某欄 → sort | uniq -c 統計 → head 看頭`。記住這條,具體參數用到再查。

---

## 1. `grep` —— 篩選行

| 命令 | 作用 |
|---|---|
| `grep -i foo` | 忽略大小寫 |
| `grep -r foo .` | 遞迴整個目錄 |
| `grep -n foo` | 帶行號 |
| `grep -v foo` | **反向**:排除含 foo 的行 |
| `grep -c foo` | 只回**計數** |
| `grep -o 'pat'` | 只印**匹配到的部分**(不是整行) |
| `grep -C 3 foo` | 連同**上下各 3 行**(`-A` 後 `-B` 前) |
| `grep -F 'a.b'` | 當**固定字串**(不解析正則,更快) |
| `grep -E 'a\|b'` | 擴展正則(`egrep`) |

> 現代替代:**`rg`(ripgrep)** 快很多、自動忽略 `.gitignore`,大倉庫搜代碼首選。語法跟 grep 近似。

---

## 2. `awk` —— 按欄位處理(最該學的一個)

`awk` 自動把每行切成欄位 `$1 $2 …`(`$0` 是整行)。你只要說「**對每行做什麼**」,需要的話再加「**最後 END 做什麼**」。

| 命令 | 作用 |
|---|---|
| `awk '{print $1, $7}'` | 印第 1、7 欄(預設按空白切) |
| `awk -F: '{print $1}'` | 指定分隔符(`:`),印第 1 欄 |
| `awk '$9 >= 500'` | **條件過濾**:第 9 欄 ≥ 500 的行(揪 5xx) |
| `awk '{sum+=$1} END{print sum}'` | 累加第 1 欄,結束時印總和 |
| `awk '{a[$1]++} END{for(k in a) print a[k], k}'` | **分組計數**(按第 1 欄) |
| `awk 'NR>1'` | 跳過表頭(`NR` = 行號) |

> 心法:`awk '模式 {動作}'`——**模式決定「哪些行」,動作決定「做什麼」**,`END{}` 收尾算總帳。求和/分組統計用它,別開 Excel。

---

## 3. `sed` —— 流編輯

| 命令 | 作用 |
|---|---|
| `sed 's/old/new/g'` | 全行替換(`g`=每行所有匹配) |
| `sed -n '10,20p'` | 只印第 10–20 行 |
| `sed '/pat/d'` | 刪掉匹配的行 |
| `sed -n '/START/,/END/p'` | 印兩個標記之間的區間 |
| `sed -i 's/a/b/g' file` | **原地修改檔案** ⚠️ |

> ⚠️ **`-i` 直接改檔、不可逆**。先**不加 `-i` 跑一遍**確認輸出對,再加。macOS 的 `sed -i` 要寫成 `sed -i '' '...'`(BSD 版要求備份後綴參數)。

---

## 4. 管道工具箱(黏合劑)

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `sort` / `sort -n` / `sort -rn` | 排序 / 按數字 / 數字逆序 | `uniq` 之前**必須先 sort** |
| `uniq -c` | 去重並**計數** | 只看相鄰行,所以要先排序 |
| `cut -d: -f1` | 按分隔符取欄(輕量版 awk) | 簡單取欄用它就夠 |
| `tr 'a-z' 'A-Z'` / `tr -d ' '` | 字符轉換 / 刪除 | — |
| `wc -l` | 數行數 | `-w` 數詞、`-c` 數位元組 |
| `tail -f` | 跟隨檔案新增 | 看實時日誌;`tail -n +2` 從第 2 行起 |
| `xargs cmd` | 把**標準輸入變成參數** | `find … \| xargs rm`;原語 3 的關鍵黏合 |
| `xargs -I{} cmd {} x` | 用 `{}` 占位逐個處理 | 需要把每項插到命令中間時 |
| `xargs -P 4` | **並行**跑 4 個 | 批量處理提速 |
| `tee file` | 邊輸出到螢幕邊存檔 | `... \| tee log \| ...` 中途留底 |

> `find ... -print0 | xargs -0` 配對使用,**處理含空格/特殊字元的檔名**不出錯——這是 `xargs` 的標準安全寫法。

---

## 5. 經典一行流(背這幾條就很能打)

```bash
# 日誌裡訪問量 top 10 的 IP(access.log 第 1 欄是 IP)
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head

# HTTP 狀態碼分佈(第 9 欄是 status)
awk '{print $9}' access.log | sort | uniq -c | sort -rn

# 找出所有含 TODO 的檔案,統計各自行數
grep -rl TODO . | xargs wc -l

# 找出並殺掉一批進程(回扣 01;先 pgrep 確認再接 kill)
pgrep -f 'my-worker' | xargs kill

# 即時看日誌裡的錯誤
tail -f app.log | grep -i --line-buffered error
```

> `sort | uniq -c | sort -rn` 是**「統計 top-N」的萬能套路**——任何「哪個出現最多」的問題都是它。

---

## 6. `jq` —— JSON 界的 awk

API、k8s、雲 CLI 全是 JSON,`jq` 是必備:

| 命令 | 作用 |
|---|---|
| `jq '.name'` | 取欄位 |
| `jq -r '.name'` | **raw**:去掉引號(給腳本用) |
| `jq '.items[].metadata.name'` | 遍歷陣列取欄位 |
| `jq 'select(.status >= 500)'` | 條件過濾 |
| `jq 'keys'` / `jq 'length'` | 看有哪些 key / 陣列長度 |

```bash
curl -s api/users | jq -r '.[] | "\(.id)\t\(.name)"'   # 拼成表格
kubectl get pods -o json | jq '.items[].metadata.name' # 配 k8s(見 08)
```

> 對應的 YAML 版工具是 `yq`(語法近似)。

---

## 深挖

- 正則表達式系統學(grep/sed/awk 都靠它) → **`regex`**
- Shell 腳本、變數、流程控制 → **`linux-handson/10-shell-scripting`**
- 找進程後批量操作 → **`01`**(`pgrep`/`pkill`)
