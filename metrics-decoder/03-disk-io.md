# 磁碟 IO 指標逐欄解碼 —— `iostat -xz` 的 `await` / `aqu-sz` / `%util`

> CPU 那行的 `wa` 告訴你「卡在 IO」,但要往下鑽得看 `iostat -xz 1`——一排 `r/s w/s rkB/s wkB/s await aqu-sz %util`。最大的坑是 **`%util` 看著 100% 你以為磁碟爆了,其實還早**。這份拆開磁碟那幾欄,核心是:**判斷飽和看 `await` + `aqu-sz`,不是 `%util`。**

---

## ① 逐欄解碼表

### `iostat -xz 1`(每裝置一行)

| 欄 | 意思 | 看點 | 原語 |
|----|------|------|------|
| `r/s` `w/s` | 每秒讀 / 寫**次數**(IOPS) | 多少筆操作 | |
| `rkB/s` `wkB/s` | 每秒讀 / 寫**量**(吞吐) | 帶寬用了多少 | |
| `r_await` `w_await` | 讀 / 寫**平均耗時**(ms) | **延遲關鍵**:排隊+服務 | [B](#原語-bawait-拆解--佇列深度little-定律) |
| `aqu-sz` | 平均**佇列深度**(在飛請求數) | **排隊鐵證**:>1 持續 = 在等 | [B](#原語-bawait-拆解--佇列深度little-定律) |
| `rareq-sz` `wareq-sz` | 平均**單次請求大小**(kB) | 大=順序,小=隨機 | [A](#原語-aio-請求的一生應用--page-cache--block-層--裝置) |
| `rrqm/s` `wrqm/s` | 每秒被**合併**的請求數 | block 層把相鄰小 IO 併大 | [A](#原語-aio-請求的一生應用--page-cache--block-層--裝置) |
| `%util` | 裝置「至少一個請求在處理」的時間比 | ⚠️ **陷阱**:高 ≠ 飽和(見原語 C) | [C](#原語-cutil-陷阱為什麼-100-不代表飽和) |

### `vmstat 1` 的 io / procs 區

| 欄 | 意思 | 看點 | 原語 |
|----|------|------|------|
| `bi` `bo` | 每秒**塊**讀入 / 寫出 | 整機 IO 量(不分裝置) | |
| `b` | **不可中斷睡眠(D 狀態)**的進程數 | >0 持續 = 一堆進程卡在 IO | [D](#原語-dwriteback--fsync--d-狀態為什麼-write-快卻偶爾卡死) |

### 去哪看

```bash
iostat -xz 1             # -x 擴展欄(await/aqu-sz/%util),-z 隱藏全閒的裝置
iotop                    # 哪個進程在狂讀寫(需 root)
pidstat -d 1             # 每進程的 kB_rd/s kB_wr/s
ps -eo pid,stat,comm | grep ' D'   # 找 D 狀態(卡 IO)的進程
```

真機 `iostat -xz 1`,寫負載中(本次容器,`stress-ng --hdd`):
```
Device   r/s   w/s    wkB/s   w_await  wareq-sz  aqu-sz  %util
vdb     0.00  88.00 317152.0    0.00    3604.0    0.00   90.40
                └ 317 MB/s 大塊順序寫    └等待≈0  └佇列≈0  └忙了90%…但沒人在等!
```

---

## ② 原語黑盒

### 原語 A:IO 請求的一生(應用 → page cache → block 層 → 裝置)

**① 你視角**
你 `write(fd, buf, 4KB)` 一行就返回了,感覺像直接寫進磁碟。其實沒有——它走了好幾層,而且多半根本還沒到磁碟。

**② 黑盒內部**
一次 IO 的路徑:

```
應用 read/write
   ↓ syscall(計入 sy)
page cache —— 讀:命中就直接回(不碰盤);寫:寫進快取標 dirty 就返回(見原語 D)
   ↓ 真要落盤時
block 層 —— 把相鄰請求【合併】(rrqm/wrqm)、【排序】、按【IO 調度器】排佇列
   ↓
裝置驅動 → 硬件(SSD/NVMe/機械盤)
```

幾個欄就是這條路的讀數:
- `rareq-sz`/`wareq-sz` 大 = 順序大塊(高效);小(如 4kB)= 隨機小 IO(機械盤上很慢)。
- `rrqm/s`/`wrqm/s` = block 層幫你把多個相鄰小 IO **合併**成大請求,減少裝置操作數。

**③ 砸實**
本次寫負載 `wareq-sz=3604`(每次寫 ~3.6MB 大塊)、`wkB/s=317152`(~317MB/s)——典型順序大寫,所以單次請求很大、吞吐很高。

---

### 原語 B:await 拆解 + 佇列深度(Little 定律)

**① 你視角**
「磁碟慢」到底慢在哪?是設備本身慢,還是請求在排隊等?這兩個要分開。

**② 黑盒內部**
`await` = 一個 IO 從**進佇列**到**完成**的總時間 = **排隊等待 + 設備服務**兩段之和。

`aqu-sz`(平均佇列深度)= 平均有幾個請求**同時在飛**。這正是 **Little 定律**:

```
aqu-sz = (r/s + w/s) × await       (在途 = 到達率 × 停留時間)
```

所以判讀:
- `await` 高 + `aqu-sz` 高 → 請求在**排隊**(來不及處理,堆積)= 真飽和。
- `await` 高 + `aqu-sz` ≈1 → 設備**本身慢**(單個請求就耗時),不是排隊。
- `await` 低 → 不管 `%util` 多高,**沒人在等**,健康。

**判斷磁碟有沒有撐不住,看 `await` 和 `aqu-sz`,這才是延遲和排隊。**

**③ 砸實**
本次 `%util=90.40`,但 `w_await=0.00`、`aqu-sz=0.00`——設備忙著搬 317MB/s,**但沒有任何請求在等**。延遲視角看,完全沒飽和(見下一個原語為什麼)。

---

### 原語 C:%util 陷阱(為什麼 100% 不代表飽和)

**① 你視角**
你看到 `%util=99%`,第一反應「磁碟滿了!」。在 SSD/NVMe 上,這個結論常常是錯的。

**② 黑盒內部**
`%util` 的定義是:**統計區間內,裝置「至少有一個請求在處理」的時間佔比**。

這個定義來自**單佇列機械盤**時代:那時磁碟一次只能處理一個請求,`%util=100%` = 一刻不停 = 真飽和。

但現代 **SSD/NVMe 有多個硬件佇列,能並行處理幾十上百個請求**。它「一直有請求在處理」(util=100%)時,可能還能再吃幾倍的量。所以 **`%util=100%` 在 SSD 上不等於飽和**——它只說「沒閒著」,不說「滿載」。

→ 正確姿勢:`%util` 只當「忙不忙」的粗略信號,**飽和看 `aqu-sz`(排隊)和 `await`(延遲)**。

**③ 砸實**
本次 `%util=90.40` 但 `aqu-sz=0`、`await=0`——典型「忙但沒滿」:設備在高速搬數據,卻沒有任何請求需要排隊等待。只看 `%util` 會誤判成快爆了。

---

### 原語 D:writeback / fsync / D 狀態(為什麼 `write` 快卻偶爾卡死)

**① 你視角**
你的 `write()` 平時微秒級返回,但偶爾某次卡住好幾百毫秒。為什麼同一個調用時快時慢?

**② 黑盒內部**
- 普通 `write()` = **buffered write**:數據寫進 page cache、標記 dirty 就**立即返回**(沒等磁碟)。快。
- 內核**後台 writeback** 線程稍後把 dirty 頁刷到磁碟。你的應用無感。
- 但 `fsync()` / `O_DIRECT` / 或 dirty 頁堆太多觸發強制回寫時,調用會**真的等磁碟完成**才返回。慢。這就是偶爾卡住的那次。

這也解釋了 [01-cpu 的 `wa`=0](./01-cpu.md#原語-diowaitwa):buffered write 不阻塞,CPU 不算 iowait;只有同步等盤(fsync/O_DIRECT/讀未快取)才會出現 `wa` 和 `D` 狀態。

**`D` 狀態(不可中斷睡眠)**:進程正卡在內核 IO 路徑裡等硬件,連 `kill -9` 都殺不掉(要等 IO 回來)。`vmstat` 的 `b` 列 = D 狀態進程數;一堆 `D` = IO 子系統頂不住。

**③ 砸實**
本次 `vmstat`:寫負載時 `bo=324164`(塊在寫出),但 `b=0`、`wa=0`——因為是 buffered writeback,沒人同步等盤。要看到 `b`/`wa` 升,得 fsync 密集或真慢盤。

---

## ③ 決策樹收口

```
CPU 那行 wa 高 / 應用慢疑似卡 IO
│
└─ iostat -xz 1
    ├─ await 高 + aqu-sz 高(>1 持續)  → 在排隊,設備頂不住    → 找元兇    [原語 B]
    ├─ await 高 + aqu-sz ≈1            → 設備本身慢(慢盤/NFS)            [原語 B]
    ├─ %util 高 但 await/aqu-sz 低     → 忙但沒飽和,別誤判!  (SSD 常見)  [原語 C]
    └─ 找元兇 → iotop / pidstat -d 1;ps 看 D 狀態                        [原語 A·D]
```

> 一句心法:**`%util` 只看「忙不忙」,飽和與否看 `await`(延遲)+ `aqu-sz`(排隊)。**

---

## ④ 面試複習(只自檢)

1. `%util=100%` 一定代表磁碟飽和嗎?在 SSD 上為什麼可能不是?
2. `await` 包含哪兩段時間?`aqu-sz` 和 Little 定律什麼關係?
3. 為什麼 `write()` 平時很快、偶爾卡幾百毫秒?
4. `D` 狀態進程是什麼?為什麼 `kill -9` 殺不掉?
5. `wareq-sz` 很小(如 4kB)說明什麼 IO 模式?在機械盤上有什麼後果?

<details>
<summary>對答案</summary>

1. 不一定。`%util` 是「至少一個請求在處理」的時間比,源自單佇列機械盤。SSD/NVMe 多佇列能並行,util=100% 也可能還能吃更多。看 await/aqu-sz。
2. `await` = 排隊等待 + 設備服務。`aqu-sz`(平均佇列深度)= (r/s+w/s) × await,就是 Little 定律的在途數。
3. 平時 buffered write 進 page cache 就返回;偶爾 fsync 或 dirty 堆積觸發強制回寫,真等磁碟完成才返回。
4. 不可中斷睡眠,卡在內核 IO 路徑等硬件。信號要等它從內核態回來才能處理,所以 kill -9 當下殺不掉。
5. 隨機小 IO。機械盤要不停尋道,IOPS 上不去、await 飆高;這正是隨機讀寫慢的根源。

</details>

---

## 回鏈

- **fd / VFS / write→page cache→writeback 路徑原語** → [`../linux/03-io-primitives`](../linux/03-io-primitives/)
- **Page Cache / IO 調度 / fsync 機制** → [`../performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md`](../performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md)
- **iostat / iotop 工具更深** → [`../performance-tuning-roadmap/02-linux-tools/03-disk-tools.md`](../performance-tuning-roadmap/02-linux-tools/03-disk-tools.md)
- **快速反查** → [`../cli-toolbox/02-performance-and-resource-triage.md`](../cli-toolbox/02-performance-and-resource-triage.md)
- 上一章 [02 記憶體](./02-memory.md) · 下一章 [04 網路](./04-network.md)
