# 記憶體指標逐欄解碼 —— `free` / `vmstat` 的 `si so` / `VIRT RES`

> 你打 `free -m` 看到一排 `total used free buff/cache available`,或 `top` 裡每個進程的 `VIRT RES SHR`——最坑的是 **`free` 很低你以為記憶體不夠,其實沒事**;還有 `VIRT` 動輒幾個 G 但其實沒佔那麼多。這份把記憶體那幾欄拆開,核心是兩個反直覺:**「free 低是正常的」**和**「VIRT 不是真佔用」**。

讀法同 [01-cpu](./01-cpu.md):急查看 ①,搞懂底層看 ②,動手看 ③。

---

## ① 逐欄解碼表

### `free -m`(整機記憶體)

| 欄 | 意思 | 看點 | 原語 |
|----|------|------|------|
| `total` | 總物理記憶體 | — | |
| `used` | 已用(約 = total − free − buff/cache) | 不含可回收快取 | |
| `free` | **完全沒被碰過**的記憶體 | **低是正常的!** 別拿它判斷夠不夠 | [B](#原語-bpage-cache-與-available為什麼-free-總是很低) |
| `shared` | tmpfs / 共享記憶體 | — | |
| `buff/cache` | Linux 拿空閒記憶體當的**檔案快取** | 看著佔很多,但隨時可回收 | [B](#原語-bpage-cache-與-available為什麼-free-總是很低) |
| `available` | **真正還能用的**(≈ free + 可回收 cache) | **判斷夠不夠看這個** | [B](#原語-bpage-cache-與-available為什麼-free-總是很低) |

### `vmstat 1` 的 memory / swap 區

| 欄 | 意思 | 看點 | 原語 |
|----|------|------|------|
| `swpd` | 已用 swap 量 | 持續增長 = 記憶體在外溢到磁碟 | [C](#原語-cswapsi--so) |
| `free`/`buff`/`cache` | 同上 | — | |
| `si` | **swap-in**(從磁碟換頁回記憶體) | ⚠️ **不是** top 的 softirq! | [C](#原語-cswapsi--so) |
| `so` | **swap-out**(把記憶體頁寫去磁碟) | `si`/`so` 持續非零 = 記憶體真不夠 | [C](#原語-cswapsi--so) |

### `top` 每進程(按記憶體看)

| 欄 | 全名 | 意思 | 原語 |
|----|------|------|------|
| `VIRT` | virtual(=`ps` 的 VSZ) | **申請**的虛擬地址空間總大小(含未觸碰、共享庫、mmap 檔案) | [A](#原語-a虛擬記憶體virt-vs-res) |
| `RES` | resident(=`ps` 的 RSS) | **實際佔用**的物理記憶體 | [A](#原語-a虛擬記憶體virt-vs-res) · [E](#原語- erss-計量陷阱可選) |
| `SHR` | shared | RES 裡與別人共享的部分(共享庫等) | [E](#原語-erss-計量陷阱可選) |
| `%MEM` | — | `RES / total` | |

### ⚠️ `si` 撞名(和 01-cpu 那個又撞一次)

- `vmstat` 的 `si` = **s**wap-**i**n(換頁進記憶體,本章)
- `top` 的 `si` = **s**oft**i**rq(軟中斷,見 [01-cpu 原語 B](./01-cpu.md#原語-b中斷hi--si))

### 去哪看

```bash
free -m -w               # -w 把 buff 和 cache 分開兩欄;盯 available
vmstat 1                 # memory 區 + swap 的 si/so
top                      # 按 M 鍵依 %MEM 排序;看 VIRT/RES/SHR
cat /proc/meminfo        # 最權威:MemTotal/MemFree/MemAvailable/Cached/...
cat /proc/<pid>/status   # 單進程:VmSize(=VIRT) VmRSS(=RES) VmSwap
```

真機 `free -m`(本次容器,8G 機):
```
       total   used   free  shared  buff/cache  available
Mem:    8005    592   6560      36         852       7176     ← free 6560 但 available 7176(cache 也能用)
Swap:   9029      0   9029
```

---

## ② 原語黑盒

### 原語 A:虛擬記憶體(`VIRT` vs `RES`)

**① 你視角**
你在 Java `new byte[1<<20]`、或 C `malloc(2GB)`——這一步**幾乎瞬時**,不管你機器有沒有 2GB。為什麼這麼快?因為這時根本沒給你真的物理記憶體。

**② 黑盒內部**
每個進程有自己的**虛擬地址空間**(一大片假的、連續的地址)。`malloc`/`mmap` 只是在這片虛擬空間裡**劃一塊範圍**(記進 `VIRT`),不立即分配物理頁。

真正第一次**寫**某一頁時,CPU 發現該頁沒有物理頁對應(頁表 present bit=0)→ 觸發**缺頁異常(page fault)**→ 內核這才分配一頁真物理記憶體,計入 `RES`。這叫**按需分頁(demand paging)**。

所以:
- `VIRT` = 你**申請**了多少地址空間(含共享庫、`mmap` 的整個檔案、還沒碰的堆)。常常虛高。
- `RES` = 你**真正佔用**了多少物理記憶體。判斷「這進程吃多少記憶體」看 `RES`,不是 `VIRT`。
- 「`VIRT` 2G 但 `RES` 200M」**完全正常**——申請多、實用少。

> page fault 的 minor/major 細節在 [`../linux/01-memory-primitives`](../linux/01-memory-primitives/)。

**③ 砸實**
分配並寫滿 2GB(`stress-ng --vm 2 --vm-bytes 1g --vm-keep`):
```
   PID USER     VIRT    RES   SHR S  %MEM  COMMAND
  3463 root   673452 591244  968 R   7.2  stress-ng    ← 每個 worker VIRT≈658M RES≈577M
```
這例 `RES` 接近 `VIRT`,因為 `--vm-keep` 把分配的頁全寫過了(全部缺頁、全部落地)。一般應用 `VIRT` 會比 `RES` 大得多(共享庫、未觸碰的堆)。

---

### 原語 B:page cache 與 available(為什麼 `free` 總是很低)

**① 你視角**
你新裝的機器啥都沒跑,`free` 卻顯示記憶體用了一大半。是誰偷了?沒人偷——是 Linux **故意**把空閒記憶體拿去當檔案快取了。

**② 黑盒內部**
你讀過 / 寫過的檔案,內核會把它的內容**留在記憶體裡**(page cache,顯示在 `buff/cache`),下次讀同一檔案直接命中記憶體,不碰磁碟。

關鍵:**這部分記憶體隨時可回收**——一旦有進程真要記憶體,內核立刻把乾淨的快取頁丟掉讓出來。所以:
- `free`(完全沒碰過的)很低 = **正常**,因為閒著也是閒著,拿來快取。
- `available`(`free` + 可回收快取)才是**真正還能給應用用的量**。

**判斷記憶體夠不夠,看 `available`,不是 `free`。** 這是最常見的誤判。

**③ 砸實**
讀一個 512MB 檔案前後對比:
```
        free   buff/cache  available
before  6559        853       7176
after   6028       1380       7172     ← cache +530M, free −530M, 但 available 幾乎不變!
```
快取吃掉了 free,可 `available` 紋風不動——因為那 530M 快取要用隨時能還。**這就是「free 低別慌」的鐵證。**

---

### 原語 C:swap(`si` / `so`)

**① 你視角**
記憶體真的塞滿了會怎樣?內核把**很久沒用的**記憶體頁寫到磁碟上一塊區域(swap),騰出物理記憶體。

**② 黑盒內部**
- **swap-out(`so`)**:RAM → 磁碟(踢出冷頁)。
- **swap-in(`si`)**:程式又要用那塊記憶體 → 從磁碟讀回 RAM。

為什麼是災難:磁碟比 RAM 慢約 **10 萬倍**。一旦工作集被反覆換進換出(**thrashing**),每次存取記憶體都可能變成磁碟 IO → 性能斷崖式雪崩。

`vm.swappiness`(0~100)控制內核多積極用 swap;生產常調低(10 甚至更低)甚至關閉,寧可早點 OOM 也不要 thrashing 拖垮整機。

→ `vmstat` 的 `si`/`so` **持續非零 = 記憶體真的不夠了**,正在拿磁碟硬頂。這是「記憶體不足」最硬的信號(比 `free` 低可靠得多)。

**③ 砸實(誠實:本次沒逼出 swap)**
本次分配 2GB 時 `vmstat` 的 `si`/`so` 全 `0`——8G 機分 2G 還沒到壓力點,加上有 9G swap 空著。要逼出 `si`/`so`,得分配超過物理記憶體。真機上記憶體吃緊時:
```bash
vmstat 1     # si/so 持續 >0 = 在 thrashing,記憶體不夠
```
> 註:這台 `iostat` 裡有個 `zram0` 裝置——OrbStack 用 **zram**(壓縮記憶體當 swap)做交換,比真磁碟 swap 快。雲主機 / 裸機多是磁碟或 SSD swap 分區。

---

### 原語 E:RSS 計量陷阱(可選)

**① 你視角**
你把 `top` 裡所有進程的 `RES` 加起來,發現**遠超過實體記憶體**。記憶體穿越了?

**② 黑盒內部**
共享庫(如 `libc`)的物理頁被**所有進程共享**——只有一份在物理記憶體,但**每個進程的 `RES` 都把它算進去**。所以把各進程 `RES` 相加會**重複計算**共享部分。

要不重複計算,看 **PSS(Proportional Set Size)**:共享頁按使用進程數均攤。
```bash
cat /proc/<pid>/smaps_rollup    # 看 Pss 行
```
`SHR` 欄就是 `RES` 裡屬於共享的那部分。

---

## ③ 決策樹收口

```
懷疑記憶體問題
│
├─ 夠不夠?           → 看 available(不是 free!)              [原語 B]
│   └─ available 低 + vmstat si/so 持續非零 → 記憶體真不夠     [原語 C]
│
├─ 誰吃的?           → ps aux --sort=-%mem | head;top 按 M    [原語 A]
│   └─ 看 RES(不是 VIRT);持續漲 = 疑似洩漏
│
├─ 加起來超過實體?   → 共享庫重複計;看 PSS(smaps_rollup)     [原語 E]
│
└─ 進程被殺了?       → dmesg | grep -i 'killed process'       (OOM killer)
                        /proc/<pid>/oom_score 看誰最容易被殺
```

> 一句心法:**`free` 看 `available`,夠不夠的鐵證是 `si`/`so`,進程佔用看 `RES` 不看 `VIRT`。**

---

## ④ 面試複習(只自檢)

1. `free` 顯示 `free` 很低,代表記憶體不夠嗎?該看哪一欄?
2. 一個進程 `VIRT` 2G 但 `RES` 200M,正常嗎?為什麼(用按需分頁解釋)?
3. `vmstat` 的 `si` 和 `top` 的 `si` 是同一個嗎?
4. 為什麼把所有進程的 `RES` 加起來會超過實體記憶體?怎麼正確算?
5. 生產為什麼常把 `swappiness` 調很低甚至關 swap?

<details>
<summary>對答案</summary>

1. 不代表。`free` 是「完全沒碰過」的,Linux 故意拿空閒記憶體當快取所以 `free` 總是低。看 `available`(free + 可回收快取)。
2. 正常。`malloc`/`mmap` 只劃虛擬地址(VIRT),真寫某頁才缺頁分配物理頁(RES)。申請多、實用少。
3. 不是。`vmstat si`=swap-in(換頁進記憶體);`top si`=softirq(軟中斷)。
4. 共享庫物理頁只一份但每個進程 RES 都算,相加重複計。看 PSS(`/proc/<pid>/smaps_rollup`)按進程均攤。
5. 避免 thrashing:swap 比 RAM 慢 10 萬倍,反覆換頁會拖垮整機;寧可早 OOM 殺一個進程也不要全機卡死。

</details>

---

## 回鏈

- **虛擬記憶體 / 缺頁 / brk·mmap 原語更深** → [`../linux/01-memory-primitives`](../linux/01-memory-primitives/)
- **Swap / swappiness / OOM killer 機制** → [`../performance-tuning-roadmap/00-os-fundamentals/02-memory-management.md`](../performance-tuning-roadmap/00-os-fundamentals/02-memory-management.md)
- **動手:VSZ 2G 但 RSS 200M 正常嗎** → [`../linux-handson/04-memory-model`](../linux-handson/04-memory-model/)
- **快速反查** → [`../cli-toolbox/02-performance-and-resource-triage.md`](../cli-toolbox/02-performance-and-resource-triage.md)
- 上一章 [01 CPU](./01-cpu.md) · 下一章 [03 磁碟 IO](./03-disk-io.md)
