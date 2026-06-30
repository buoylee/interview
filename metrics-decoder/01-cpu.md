# CPU 那行逐欄解碼 —— `us sy ni id wa hi si st`

> 你打 `top`,頂部第三行是 `%Cpu(s): ... us, ... sy, ... id ...`;或 `vmstat 1` 最右邊那塊 `us sy id wa st`。**這一行是「機器慢」最高頻的第一眼判讀**——但除了 `us`/`sy`,其他欄你多半似懂非懂。這份把 8 個欄全拆開:每欄什麼意思、高了代表什麼、**背後那個原語黑盒裡到底發生什麼**。

讀法:急著查 → 看 [① 逐欄解碼表](#-逐欄解碼表)。想搞懂底層 → 往下看 [② 原語黑盒](#-原語黑盒)。看完怎麼動 → [③ 決策樹](#-決策樹收口)。

---

## ① 逐欄解碼表

`top` 顯示順序是 `us sy ni id wa hi si st`(8 欄)。底層 `/proc/stat` 還多兩欄 `guest`/`guest_nice`,`top` 不單獨顯示。

| 欄 | 全名 | 一句話 | 高了代表什麼 | 背後原語 |
|----|------|--------|--------------|----------|
| `us` | user | **用戶態** CPU | 你的應用在燒 CPU(算法、序列化、加解密、正則、GC) | [A](#原語-a用戶態-vs-內核態us-vs-sy) |
| `sy` | system | **內核態** CPU | syscall 太頻 / 上下文切換太多(海量小 IO、建線程、fork 風暴) | [A](#原語-a用戶態-vs-內核態us-vs-sy) · [C](#原語-c上下文切換--調度sy--ni--id) |
| `ni` | nice | 跑**低優先**(正 nice)任務的時間 | 有被 `nice` / `renice` 調低優先級的 user 進程在吃 CPU | [C](#原語-c上下文切換--調度sy--ni--id) |
| `id` | idle | **空閒** | CPU 沒事幹(這是好事,除非你期望它在忙) | [C](#原語-c上下文切換--調度sy--ni--id) |
| `wa` | iowait | CPU 空閒、**但在等磁碟 IO** | **IO 瓶頸**——不是 CPU 不夠,是磁碟/NFS 慢 | [D](#原語-diowaitwa) |
| `hi` | hardirq | **硬中斷**處理 | 硬件中斷風暴(壞網卡/磁碟、極高包率) | [B](#原語-b中斷hi--si) |
| `si` | softirq | **軟中斷**處理 | 絕大多數是**網路收包**;單核 `si` 100% = 經典網路瓶頸 | [B](#原語-b中斷hi--si) |
| `st` | steal | 你的 vCPU **被宿主搶走**的時間 | 雲主機被超賣 / 鄰居吵——**應用層使不上力** | [E](#原語-e虛擬化-stealst) |
| `guest` | guest | 替**虛擬機**跑 vCPU 的時間 | 只有你本身是 KVM/QEMU 宿主進程才非 0 | [E](#原語-e虛擬化-stealst) |

> 八欄相加 = 100%(每個 CPU 把每一刻的時間歸進這幾類之一)。

### ⚠️ `si` 撞名陷阱(最坑)

`si` 在兩個工具裡是**完全不同的兩回事**:

- `top` 的 `si` = **s**oft**i**rq(軟中斷)→ 多半是網路收包(看 [原語 B](#原語-b中斷hi--si))
- `vmstat` 的 `si` = **s**wap-**i**n(從磁碟換頁回記憶體)→ 記憶體不夠的信號(屬記憶體章)

純縮寫巧合,機制毫無關係。**看到 `si` 先認清是哪個工具的。**

### 去哪看這一行

```bash
top                      # 頂部 %Cpu(s) 那行(按 1 可拆每核)
vmstat 1                 # 最右 us sy id wa st(少了 ni/hi/si,但有 r b in cs)
mpstat -P ALL 1          # 每核拆,欄最全:%usr %nice %sys %iowait %irq %soft %steal %guest %idle
cat /proc/stat           # 原始累計值,第一行 cpu 後依序:user nice system idle iowait irq softirq steal guest guest_nice
```

真機 `/proc/stat` 第一行長這樣(本次容器實跑):
```
cpu  1373632 1 865871 302885114 37170 0 187587 0 0 0
     └user   │ └system └idle    └iow  │ └softirq └steal
            nice                  irq            (guest/guest_nice=0)
```
注意這台 `irq`(硬中斷累計)是 0、`steal` 是 0——下面原語 B / E 會解釋為什麼這環境看不到。

---

## ② 原語黑盒

只挑那幾個「似懂非懂」的欄,把底層講透。每個原語三層:**你視角(Java/Go 橋)→ 黑盒內部 → 砸實(真機輸出)**。

### 原語 A:用戶態 vs 內核態(`us` vs `sy`)

**① 你視角**
你的 Java 算 hash、序列化 JSON、跑正則、GC——這些是**你的代碼自己在算**,計入 `us`。
但你一旦 `read()`/`write()` 檔案、開 socket、`new Thread()`、`malloc` 大塊記憶體——這些**你做不到,得求內核**,計入 `sy`。

**② 黑盒內部**
CPU 有特權級:你的代碼跑在**低權級**(x86 的 ring 3 / aarch64 的 EL0),碰不了硬件。要碰,就執行一條 `syscall` 指令 → CPU **切到高權級**(ring 0 / EL1)、跳進內核入口 → 內核替你幹完 → 返回你的代碼。

每次系統調用 = 一趟 `用戶態 → 內核態 → 用戶態` 往返,這趟的內核側時間就是 `sy`。

所以:
- `us` 高 = 純計算重 → 拿 `perf` / 火焰圖找哪段代碼在燒。
- `sy` 高 = **syscall 太頻**(每秒幾十萬次小 `read`/`write`、瘋狂建線程、fork 風暴),或上下文切換多(見原語 C)→ 拿 `strace -c` 看狂調哪個 syscall。

**③ 砸實**
純用戶態計算(`stress-ng --cpu`,10 核):
```
 r  b ...  in   cs us sy id wa st
10  0 ... 9271   60 100  0  0  0  0      ← us=100, sy≈0:純算,幾乎不碰內核
```
```
# pidstat 1 —— 每進程拆 %usr / %system
 UID  PID    %usr %system  %CPU  Command
   0 1081  100.00    0.00 100.00 stress-ng    ← %system=0 → 全在 us
```
對照「狂切換」負載(下面原語 C),`sy` 會跳到 35——因為切換本身是內核幹的活。

---

### 原語 B:中斷(`hi` / `si`)

**① 你視角**
你的代碼在順序跑。這時網卡收到一個封包 / 磁碟讀完 / 定時器到期——CPU 怎麼知道?
不是靠你的代碼一直輪詢「好了沒?好了沒?」(那浪費 CPU),而是**硬件主動發信號打斷 CPU**。這個機制 ≈ 你熟的 **event callback / 中斷回調**,不是 busy-wait。

**② 黑盒內部**
中斷處理拆成兩半,因為「要快」和「活很重」矛盾:

- **硬中斷(hardirq → `top` 的 `hi`)**:設備拉一根電信號(IRQ)→ CPU **立刻**存檔、跳進中斷處理。這段期間會擋住其他中斷,所以**必須極快**,只做最少的事(「收到了,封包的 DMA 地址記下」)就返回。這叫 **top-half(上半部)**。
- **軟中斷(softirq → `top` 的 `si`)**:真正的重活——解析封包、走 TCP/IP 協議棧——推遲到 **bottom-half(下半部)** 再做。此時中斷已重新打開、可被搶佔、可申請記憶體。網路收包大量走 `NAPI` 這套軟中斷。

> **一句破誤解:** 這裡的「軟中斷(softirq)」**不是硬體觸發的中斷**,而是內核自己一套**固定幾類的高優先級待辦佇列**(`NET_RX`/`TIMER`…)。硬中斷的上半部只是去佇列「打個標記:有活」,內核稍後(硬中斷返回時、或 `ksoftirqd` 執行緒裡)把待辦跑掉。名字裡的「中斷」是歷史包袱——讀成「內核的延後處理任務」就不會和硬中斷混了。

所以:
- `hi` 高 = 硬件中斷風暴(壞設備、極高包率)。
- `si` 高 = 軟中斷處理重,**絕大多數是網路收包**。單核 `si` 打到 100% 是經典網路瓶頸 → 用 **RSS / RPS** 把中斷分散到多核。

#### `hi` / `si` 什麼場景會升高?

先分清楚:**中斷次數高**不一定等於 `hi`/`si` CPU 高。`vmstat` 的 `in`、`/proc/interrupts`、`/proc/softirqs` 看的是「發生了多少次」;`top` 的 `hi`/`si` 看的是 CPU 花了多少時間處理。處理很輕時,次數高但佔比也可能不高。

| 指標形狀 | 常見場景 | 你會怎麼驗證 |
|---|---|---|
| `hi` 高,集中在某顆 CPU | 某條硬體 IRQ 打太密,常見是網卡/磁碟控制器高頻中斷、IRQ affinity 都綁到同一核 | `mpstat -P ALL 1` 看哪顆 `%irq` 高;`watch -n1 cat /proc/interrupts` 看哪條 IRQ 在暴漲 |
| `hi` 持續高,且某設備 IRQ / error counter 同時漲 | 壞網卡、壞線、磁碟/控制器重試、驅動 bug,設備一直發中斷或重置 | `/proc/interrupts` 找設備行;再看 `dmesg`、`ethtool -S <iface>`、磁碟錯誤日誌 |
| `si` 高,尤其單核高 | **網路 PPS 太高**:小包、UDP flood、L4/L7 代理高 QPS、短連接、封包被集中送到一個 RX queue/一顆 CPU | `mpstat -P ALL 1` 看哪顆 `%soft` 高;`watch -n1 cat /proc/softirqs` 看 `NET_RX` 是否暴漲;再查 RSS/RPS/IRQ affinity |
| `si` 高,`ksoftirqd/N` 也吃 CPU | 軟中斷積壓太多,硬中斷返回時來不及跑完,被丟給第 N 顆 CPU 的 `ksoftirqd` 慢慢清 | `top -H` 看 `ksoftirqd/N`;`/proc/net/softnet_stat` 看 dropped / time_squeeze 是否增加 |
| `si` 高,但不是 `NET_RX` | 不是所有 softirq 都是收包:可能是 `TIMER`(大量定時器)、`SCHED`(調度相關)、`RCU`(回調積壓)、`NET_TX`(發包/qdisc) | 直接看 `/proc/softirqs` 哪一列漲得最快,不要只猜網路 |

讀法:如果是 `hi`,先找是哪條硬體 IRQ;如果是 `si`,先看 `/proc/softirqs` 哪個類別漲。**`si` 最常見是網路收包,但真正定案靠 `NET_RX` 這行。**

**③ 砸實(誠實:容器內看不到)**
Docker / OrbStack 的虛擬層**不向容器暴露宿主機中斷表**,本次:
```
$ wc -l /proc/interrupts
0 /proc/interrupts          ← 空檔案
```
裸機 Linux 上才能:
```bash
watch -n1 cat /proc/interrupts   # 每核 × 每條 IRQ 線的累計次數,收包時網卡那行實時遞增
watch -n1 cat /proc/softirqs     # 每核 × 每類 softirq,NET_RX 暴漲通常就是網路收包壓力
```
能看到的替代信號:`vmstat` 的 **`in` 列 = 每秒中斷數**。本次純 CPU 負載時 `in≈9271`,主要是定時器 tick + 多核 IPI(核間中斷),不是網路。

---

### 原語 C:上下文切換 + 調度(`sy` / `ni` / `id`)

**① 你視角**
`Thread.sleep()`、channel 等待、或時間片用完——OS 把當前線程**摘下**、換另一個上來跑。換的瞬間要先把「當前線程跑到哪(寄存器、棧位置)」存起來,再恢復下一個線程上次的狀態。這個存+恢復 = **上下文切換**。

**② 黑盒內部**
內核給每個線程一個 `task_struct`,裡面存它的 CPU 寄存器快照、棧指針、調度狀態。切換 = 存當前的 `task_struct` + 載入下一個。

這三個詞不要背黑話,按「讓線程下次能從原地繼續跑」理解:

| 保存什麼 | 白話 | 為什麼切換時要存 |
|---|---|---|
| CPU 寄存器快照 | CPU 當下的「工作台」:下一條指令在哪(`rip`/PC)、臨時值在哪(`rax`/`rbx` 等)、當前棧頂在哪(`rsp`/SP) | 不存的話,下次切回來不知道程式執行到哪、臨時變量也丟了 |
| 棧指針 | 這個線程自己的調用棧目前頂到哪一格 | 函數返回、局部變量、調用鏈都靠棧;換線程時要換到另一條線程自己的棧 |
| 調度狀態 | 這個任務現在是 runnable、sleep、被搶佔、nice 權重、vruntime 等調度器要用的帳本 | 調度器要靠它判斷誰能跑、誰該先跑、誰還在等 IO/鎖 |

詳細版(包含通用寄存器、FPU/SIMD、`task_struct.thread`、內核棧、CR3/TLB)在 [`../linux/02-execution-primitives`](../linux/02-execution-primitives/) 的「原語四:上下文切換」。

關鍵:**真正的代價不是這幾條存/載指令,是 cache 和 TLB 變冷**——新線程的數據不在 L1/L2 cache、地址翻譯不在 TLB,得重新從記憶體撈,慢。所以切換越頻越虧。

調度器(Linux 是 **CFS**)按 `nice` 值分時間片:`nice` 越小優先級越高、權重越大(範圍 -20~19,nice -20 約是 nice 0 的 88761/1024 倍,nice 19 只有約 1/68)。

兩種切換(`pidstat -w` 分得出):
- **cswch(自願)**:線程主動讓出(等鎖、等 IO、sleep)。
- **nvcswch(非自願)**:時間片耗盡被**搶佔**。**`nvcswch` 高 = 可運行線程多於 CPU、大家在搶 = CPU 過載信號。**

對應欄:`id` = 沒線程可跑的空閒;`ni` = 跑「被調低優先級(正 nice)」進程的時間。

#### `ni` 什麼場景會升高?

`ni` 不是「所有調過優先級的時間」,而是**正 nice 值(低優先級、比較謙讓)的 user-mode CPU 時間**。也就是說,普通 nice 0 的進程燒 CPU 算 `us`;被 `nice -n 10` / `nice -n 19` 降優先級的進程燒 CPU 才算 `ni`。

| 指標形狀 | 常見場景 | 你會怎麼驗證 |
|---|---|---|
| `ni` 高,`id` 低,但服務沒慢 | 備份、壓縮、轉碼、索引、CI、批處理被故意用 `nice` 降優先級,正在把空閒 CPU 用滿 | `top` 看進程 `NI` 欄;`ps -eo pid,ni,pri,pcpu,comm --sort=-pcpu` 看前幾行,找 `NI>0` 且吃 CPU 的進程 |
| `ni` 高,線上服務也變慢 | 低優先任務太多,即使它們會讓普通任務,仍然把機器推到 CPU 飽和;或服務本身也被錯誤 `renice` 成低優先 | `pidstat -u 1` 看服務 `%wait`;`ps -o pid,ni,pri,cls,comm -p <PID>` 確認服務是否 `NI>0` |
| `ni` 一直 0 | 沒有正 nice 的進程在跑,或吃 CPU 的都是普通 nice 0 / 高優先進程 | `ps -eo pid,ni,pcpu,comm --sort=-pcpu` 看前幾行;如果 `NI` 都是 0,CPU 時間自然歸到 `us` |

兩個常見誤解:
- `ni` 高**不一定是壞事**。它常常代表你把批量任務設成低優先級,讓它們「有空就跑」。只要正常服務沒排隊、延遲沒升,這是合理利用 CPU。
- 負 nice 值(例如 `nice -n -10`,高優先級)不是這欄的典型來源;它通常仍被看成 user CPU,只是調度器更偏向先跑它。要找高/低優先進程,看 `ps` 的 `NI` 或 `top` 的 `NI` 欄。

**③ 砸實**
狂切換負載(`stress-ng --switch`):
```
 r  b ...   in       cs    us sy id wa st
 8  0 ...  6986 10618310   5 35 59  0  0     ← cs=1061萬/秒!sy 跳到 35(切換是內核活)
```
```
# pidstat -w 1 —— 每進程的兩種切換
 UID  PID   cswch/s  nvcswch/s  Command
   0 1094  703180.5   630695.0  stress-ng    ← 自願 70萬 + 非自願 63萬 /秒
```
`ni` 欄:本次沒有任何正 nice 的進程,所以 `top` 的 `ni`=0.0、`mpstat` 的 `%nice`=0.00。想看它非 0,跑 `nice -n 19 stress-ng --cpu 1`——那份 CPU 時間就會計入 `ni`。

---

### 原語 D:iowait(`wa`)

**① 你視角**
你的線程 `read()` 一個慢磁碟 / NFS,卡在那等數據回來。這段時間 CPU 在幹嘛?

**② 黑盒內部**
`wa` = **CPU 空閒、但此刻至少有一個任務卡在未完成的磁碟 IO** 的時間佔比。

理解它的鑰匙:**`wa` 是一種特殊的 idle**——CPU 沒別的事幹(所以不算 `us`/`sy`),但因為有 IO 在飛、不是真閒著,於是單獨記成 `wa`。

兩個反直覺陷阱:
- **`wa` 高 ≠ 磁碟壞了。** 可能只是應用阻塞在慢 IO,或一堆 `D` 狀態進程(不可中斷睡眠,正卡在 IO)。
- **`wa` 低 ≠ 沒有 IO 壓力。** 如果 CPU 同時有別的活幹(`us`/`sy` 高),它就不算「在等」,`wa` 反而低。`wa` 只計「沒別的事可幹、純等 IO」那部分。

**③ 砸實(誠實:這環境逼不出 `wa`)**
寫 256MB(`stress-ng --hdd`):
```
 r  b ...  bi     bo    in  cs us sy id wa st
 2  0 ...   0 323840  745 117  2  5 93  0  0     ← bo 飆到 32萬(塊寫出,IO 真在跑)…但 wa=0!
```
為什麼有 IO 卻 `wa=0`?因為這環境(OrbStack + 快存儲)的寫是**緩衝 writeback**——應用 `write()` 把數據丟進 page cache 就立刻返回,**沒有真的阻塞等盤**,所以 CPU 不算 wait。`bo`(block out)證明數據在往外寫,但 CPU 沒在等它。

這恰好實證了上面那條陷阱:**有 IO ≠ 有 iowait。** 要逼出 `wa`,得用同步直寫(`O_DIRECT` / `fsync` 每次)或真的慢盤(機械盤、跨網路 NFS)。

---

### 原語 E:虛擬化 / steal(`st`)

**① 你視角**
雲上你那顆「CPU」**不是你獨佔的實體核**。它是 hypervisor 排給你的一顆 **vCPU(虛擬 CPU)**,和同一台實體機上**鄰居 VM** 搶同一批實體核。

**② 黑盒內部**
一台實體機跑很多租戶的 VM。廠商的 **hypervisor**(KVM 等)把各 VM 的 vCPU 當成「待調度的線程」,排到真實體核上跑。

**超賣(oversubscription)**:廠商賣出的 vCPU 總數 **> 實體核數**,賭「不會所有租戶同時忙」(像航空公司超賣機位)。平時沒事。

但當鄰居也忙起來:你的 vCPU 明明**就緒、想跑**,hypervisor 卻把實體核先給了別人 → 你只能**乾等**。這段「就緒卻拿不到核」的時間 = `steal`。

兩側看同一件事:
- `top` 的 `st` = 從**被偷的客戶機**這側看(你的 vCPU 被搶走多少)。
- `mpstat` 的 `%guest` / `pidstat` 的 `%guest` = 從**宿主機替客戶機跑 vCPU** 那側看(只有 KVM/QEMU 這類進程非 0)。

`st` 高 = 鄰居太吵 / 這台機超賣嚴重。**應用層完全使不上力**(它在你的 OS 底下,你的代碼管不到)→ 修法是基建層:換規格、換可用區、換獨佔型實例。

**③ 砸實(誠實:本機復現不了)**
本次 `/proc/stat` 的 `steal`=0、`mpstat` 的 `%steal`=0.00——因為 OrbStack 沒有超賣你的核,你想跑就有核。

`st` 只在**真雲 VM 被超賣**時才非 0,本機 / Docker 造不出來。在雲上:
```bash
mpstat -P ALL 1     # %steal 持續 >0(如 5~30)就是被鄰居搶 CPU 的鐵證
```

---

## ③ 決策樹收口

看懂了每欄,排查就是一棵樹:

```
機器慢 → top(或 vmstat 1)看 CPU 那行
│
├─ us 高              → 應用在燒 CPU    → pidstat 1 揪進程 → perf / 火焰圖        [原語 A]
├─ sy 高              → 內核開銷大      → pidstat -w 看 cs;strace -c 看狂調哪個 syscall  [原語 A·C]
├─ wa 高              → IO 瓶頸         → iostat -xz 1;找 D 狀態進程             [原語 D]
├─ hi / si 高         → 中斷/軟中斷風暴 → /proc/interrupts + /proc/softirqs;網路看 si → RSS/RPS   [原語 B]
├─ st 高              → 雲被超賣搶 CPU  → 換規格 / 可用區(應用無解)             [原語 E]
├─ ni 高              → 低優先任務在吃 CPU → 找誰 NI>0;確認是否批處理/是否影響服務  [原語 C]
└─ load 高但 us+sy 都低 → 一堆 D 卡 IO   → iostat + 找 D 狀態進程                  [原語 D]
```

> 一句心法:**`top` 分流到某一欄 → 進那欄背後資源的專用工具往下鑽。** CPU 這行是分流口,不是終點。

---

## ④ 面試複習(只自檢,不塞新知)

底層都在 ② 了,這裡只回頭驗收:

1. `us` 和 `sy` 差在哪?為什麼 `sy` 高常常和上下文切換多一起出現?
2. `top` 的 `si` 和 `vmstat` 的 `si` 是同一個東西嗎?各是什麼?
3. `wa=0` 一定代表沒有 IO 壓力嗎?為什麼(用 page cache / writeback 解釋)?
4. `st` 高的時候,你在應用層能做什麼?為什麼?
5. `nvcswch`(非自願切換)很高代表系統什麼狀態?
6. 為什麼硬中斷要拆成 top-half / bottom-half 兩段?
7. `si` 高一定是網路收包嗎?怎麼確認?
8. `ni` 高一定是壞事嗎?它通常是哪類進程造成的?

<details>
<summary>對答案(展開)</summary>

1. `us`=你的代碼自己算;`sy`=陷入內核替你幹(syscall)。切換本身是內核活,且常伴隨大量 syscall/搶佔,所以 `sy` 和 `cs` 常一起高。
2. 不是。`top` 的 `si`=softirq(軟中斷,多為網路收包);`vmstat` 的 `si`=swap-in(換頁進記憶體)。
3. 不一定。CPU 若同時有別的活幹,等 IO 不計入 `wa`;緩衝 writeback 的寫根本不阻塞(本章砸實:`bo` 飆但 `wa`=0)。
4. 幾乎沒辦法。`st` 是 hypervisor 層把你的核給了鄰居,在你 OS 之下——只能換規格 / 可用區 / 獨佔實例。
5. 可運行線程多於可用 CPU,大家被時間片搶來搶去 = CPU 過載。
6. 硬中斷期間擋住其他中斷、必須極快,所以只記一筆就返回(top-half);重活推到可被搶佔、可睡眠的 bottom-half(softirq)再做。
7. 不一定。最常見是網路收包,但要看 `/proc/softirqs` 哪列漲: `NET_RX` 暴漲才是收包;也可能是 `TIMER`、`SCHED`、`RCU`、`NET_TX` 等。
8. 不一定。`ni` 高通常是正 nice 的低優先批處理在吃 CPU,例如備份、壓縮、索引、CI。它們本來就比較謙讓;只有當服務延遲升、`%wait` 高、或服務本身被錯誤設成 `NI>0` 才需要處理。

</details>

---

## 回鏈(想再深挖)

- **中斷 / 上下文切換的原語更深**(syscall 指令、特權級、task_struct、NAPI)→ [`../linux/02-execution-primitives`](../linux/02-execution-primitives/)
- **`vmstat` 的 `si`/`so`(swap)**→ 本 track [`02 記憶體`](./02-memory.md)
- **更深的工具參數**(`st` vs `%guest`、`mpstat`/`pidstat` 全欄)→ [`../performance-tuning-roadmap/02-linux-tools/01-cpu-tools.md`](../performance-tuning-roadmap/02-linux-tools/01-cpu-tools.md)
- **動手排查七段式** → [`../linux-handson/07-troubleshooting-playbook`](../linux-handson/07-troubleshooting-playbook/)
- **快速反查(不想讀原語時)** → [`../cli-toolbox/02-performance-and-resource-triage.md`](../cli-toolbox/02-performance-and-resource-triage.md)
- 下一章 [02 記憶體](./02-memory.md)
