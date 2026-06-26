# 02 · 性能與資源排查

> 機器很慢、load 飆高、`us/sy/wa` 看不懂——這章教你**先定位是哪一類瓶頸,再往下鑽**,而不是瞎猜。

---

## 收口地圖(記這三條,別背工具)

排查性能,難的不是命令,是**不知道下一步該看哪**。三條原語幫你收口:

1. **系統資源就 4 類:CPU、記憶體、磁碟 IO、網路。** 任何「慢」最後都落到這 4 類之一。排查 = 先用 `top` 分流到某一類,再進那一類的專用工具。
2. **每類資源問 3 件事(USE 法)**:用了多少(**U**tilization)、排隊多嚴重(**S**aturation)、有沒有報錯(**E**rrors)。`%CPU` 是 U,`load`/`await` 是 S——**飽和度比使用率更能解釋「卡」**。
3. **`load average` ≠ CPU 使用率。** 在 Linux 上它是「**可執行(R)+ 不可中斷(D)**」的進程數。所以 `load` 高、CPU 卻不忙,十之八九是**一堆 D 卡在 IO**。

> 一句話流程:**`top` 看 load 和 `us/sy/wa` → 判斷是 4 類裡的哪一類 → 進專用工具往下鑽。**

---

## 1. 一眼總覽:load average 怎麼讀

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| `uptime` | 看 1 / 5 / 15 分鐘 load | 三個數看**趨勢**:遞增=正在惡化,遞減=高峰已過 |
| 🔧 `top` / `htop` | 即時總覽(load + CPU + mem + 進程) | `htop` 更直觀但需安裝;`top` 人人有 |
| `nproc` | 看有幾顆邏輯 CPU | **load 要除以核心數才有意義** |

**判讀心法**:`load average` 不是百分比,是「進程數」。

- `load = 核心數` → 滿載但不排隊(剛好)
- `load > 核心數` → **有進程在排隊等**(等 CPU,或等 IO)
- 8 核機器 `load=4` 很閒;2 核機器 `load=4` 已經塞車一倍

> **Linux 的坑**:其他 Unix 的 load 只算「等 CPU」;**Linux 把 `D`(等 IO)也算進去**。所以「load 20 但 CPU 使用率才 10%」完全可能——那不是 CPU 忙,是磁碟/NFS 卡住一堆進程(往下看 `wa`)。

---

## 2. CPU:`us / sy / wa / id / st` 一行看穿瓶頸

`top` 頂部那行 `%Cpu(s)`、或 `vmstat 1` 的 CPU 區,是**整份排查最高頻的判讀**:

| 欄位 | 全名 | 高了代表什麼 |
|---|---|---|
| `us` | user | **應用程式在燒 CPU**(算法、序列化、加解密、正則、GC) |
| `sy` | system(內核態) | **系統調用 / 上下文切換太多**(海量小 IO、線程切換、fork 風暴) |
| `wa` | iowait | **CPU 閒著在等磁碟 IO** —— 不是 CPU 瓶頸,是 **IO 瓶頸** |
| `id` | idle | CPU 真的閒著 |
| `st` | steal | **虛擬機被宿主搶走的時間**(雲上高 = 鄰居吵/超賣,該換規格) |
| `ni` | nice | 被調過 nice 值的 user 時間 |

**按瓶頸分流(這是本章的核心)**:

| 症狀 | 結論 | 下一步 |
|---|---|---|
| `us` 高 | 應用在算 | `pidstat 1` 找哪個進程 → `perf` / 火焰圖往下挖(**04**) |
| `sy` 高 | 內核開銷大 | `pidstat -w 1` 看上下文切換;`strace` 看狂調哪個 syscall(**04**) |
| `wa` 高 | **IO 瓶頸** | 轉去第 4 節 `iostat -xz 1` / `iotop` |
| `st` 高 | 雲主機被超賣 | 換規格 / 換可用區,應用層使不上力 |
| load 高但 `us+sy` 都低 | **一堆 `D` 卡 IO** | `iostat` + 找 `D` 狀態進程(見 **01** STAT 欄) |

| 命令 | 作用 |
|---|---|
| 🔧 `vmstat 1` | 每秒刷:`r`(等CPU)`b`(阻塞)、`si/so`(swap)、`us/sy/id/wa/st` —— **首選總覽** |
| `mpstat -P ALL 1` | **每顆核**分開看(揪出「單核打滿、其餘閒」的單線程瓶頸) |
| `pidstat 1` | 按**進程**看 CPU(到底是誰) |

---

## 3. 記憶體:別被 `free` 嚇到

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| 🔧 `free -h` | 看記憶體用量 | **只看 `available`**,別看 `free`(見下) |
| `vmstat 1` | 看 `si`/`so`(swap in/out) | **有 swap 換進換出 = 記憶體真的不夠了**的鐵證 |
| `ps aux --sort=-%mem \| head` | 誰最吃記憶體 | 快速揪 top 記憶體大戶 |
| `pmap -x PID` | 一個進程的記憶體分佈 | 看是堆、棧、還是 mmap 的檔案 |
| `dmesg -T \| grep -i oom` | 查 OOM Killer 殺過誰 | 進程「莫名消失」先查這個 |

**判讀心法**:

- **`free` 小不等於記憶體不足**。Linux 會把空閒記憶體拿去當**檔案快取(buff/cache)**——這是好事,需要時立刻可回收。所以**看 `available`(可立即給應用用的量),不是 `free`**。
- 真正的不足訊號是**開始用 swap**:`vmstat` 的 `si/so` 持續非零 = 記憶體不夠,在拿磁碟頂,性能會雪崩。
- **RSS vs VSZ**:`VSZ` 是「虛擬地址空間/承諾」(可能很大但沒真用),`RSS` 是「真正佔的物理記憶體」——**算記憶體看 RSS**。

> 進程突然不見了?多半是 **OOM Killer**。`dmesg -T | grep -i oom` 會告訴你它殺了誰、為什麼。

---

## 4. 磁碟 IO:`wa` 高之後來這

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| 🔧 `iostat -xz 1` | 每秒看每個磁碟的詳細 IO | 看 `%util`、`await`、`r/s w/s`(見下) |
| `iotop` | 哪個**進程**在狂讀寫 | 需 root;直接揪元兇 |
| `df -h` | 看分區**剩多少空間** | 「磁碟滿」先查它(詳見 **06**) |
| `df -i` | 看 **inode** 是否用盡 | 空間還很多卻寫不進 = inode 耗盡(小檔太多) |

**關鍵指標**:

- **`await`(單次 IO 平均延遲，ms)** —— **最該看的飽和訊號**。正常 SSD 個位數 ms;飆到幾十上百 = 磁碟扛不住。
- **`%util`** —— 設備繁忙時間佔比。傳統機械盤接近 100% = 飽和;但 **NVMe/SSD 能並行,`%util` 99% 未必真飽和**,以 `await` 為準。
- `r/s` `w/s` = 每秒讀/寫次數(IOPS)。

> 串起來:**`top` 看到 `wa` 高 + `01` 裡一堆 `D` 狀態進程 → `iostat -xz 1` 確認磁碟飽和 → `iotop` 揪出是哪個進程在刷。** 這條 IO 排查鏈最常見。

---

## 5. 黃金排查路徑(把上面收成一張決策樹)

```
機器慢 → top（或 vmstat 1）
│
├─ load 高嗎？（對比 nproc）
│   ├─ us 高           → 應用燒 CPU    → pidstat 1 → perf/火焰圖 (04)
│   ├─ sy 高           → 內核開銷大    → pidstat -w / strace (04)
│   ├─ wa 高           → IO 瓶頸       → iostat -xz 1 → iotop
│   ├─ st 高           → 雲主機被搶    → 換規格/可用區
│   └─ us+sy 低但 load 高 → 一堆 D 卡 IO → iostat（同 wa 路徑）
│
└─ 記憶體？free -h 看 available
    └─ available 很低 + vmstat si/so 非零 → 真不足 → 找大戶 / 查 OOM
```

---

## 60 秒首檢清單(Brendan Gregg 的經典套路)

一台陌生機器出事,**頭 60 秒**依序敲這幾條,先有全局再深鑽:

```bash
uptime                 # 1. load 趨勢
dmesg -T | tail        # 2. 內核有沒有報錯(OOM、IO error、丟包)
vmstat 1               # 3. CPU/swap/阻塞 總覽
mpstat -P ALL 1        # 4. 是不是單核打滿
pidstat 1              # 5. 到底哪個進程在燒
iostat -xz 1           # 6. 磁碟飽和嗎(await/%util)
free -h                # 7. 記憶體 / available
# 網路那兩條(ss / sar -n DEV)見 03
```

> 工具多半在 `sysstat` 與 `procps` 套件裡(`vmstat`/`mpstat`/`pidstat`/`iostat`/`sar`)。沒裝就 `apt install sysstat` / `yum install sysstat`。

---

## 🔧 主力命令深講 + 速驗

> 性能工具的數字「沒負載時都很閒」很正常;想看數字動起來,用下面 `yes > /dev/null &` 造個 CPU 負載再觀察。**先進 README 的沙盒。**

### top — 即時總覽 + 互動鍵

`top` 跑起來後按這些鍵(這才是 top 的精髓):

| 按鍵 | 作用 |
|---|---|
| `P` | 按 CPU 排序(預設) |
| `M` | 按**記憶體**排序 |
| `1` | 展開**每顆核**分開看 |
| `H` | 顯示**線程**(而非進程) |
| `c` | 顯示完整命令列 |
| `k` | 殺進程(輸入 PID) |
| `q` | 退出 |

腳本/批量模式(不互動):

| 寫法 | 作用 |
|---|---|
| `top -b -n1` | 跑一次就退,可管道 / 存檔 |
| `top -b -n1 -o %MEM` | 按記憶體排序輸出 |
| `top -p PID` | 只盯某個進程 |

**⚡ 驗證**:
```bash
top -b -n1 | head -12      # 預期:load/任務/CPU/記憶體摘要 + 進程表頭
# 想看 us 飆到 100:造個燒 CPU 的循環再看
yes > /dev/null &
top -b -n1 | head -5       # 預期:%Cpu 區 us 接近 100,yes 在最頂
kill %1
```

### vmstat — 一行看 CPU / 記憶體 / IO 全局

| 寫法 | 作用 |
|---|---|
| `vmstat 1` | 每秒刷新(持續) |
| `vmstat 1 5` | 每秒一次,**共 5 次**後停 |
| `vmstat -w` | 寬格式,欄位不擠 |
| `vmstat -s` | 記憶體統計總覽 |

欄位記成 4 組:`r b`(等CPU/阻塞數)、`si so`(swap 換進出,非零=記憶體不足)、`bi bo`(塊設備讀寫)、`us sy id wa st`(CPU 構成,同第 2 節)。

**⚡ 驗證**:
```bash
vmstat 1 3       # 預期:刷 3 行後停;看最右 us/sy/id/wa 欄
```

### free — 記憶體用量(只看 available)

| 寫法 | 作用 |
|---|---|
| `free -h` | 人類可讀(自動 K/M/G) |
| `free -m` | 固定以 MB 顯示 |
| `free -s 2` | 每 2 秒刷一次 |

**⚡ 驗證**:
```bash
free -h          # 預期:Mem 行;重點看 "available" 欄(不是 "free" 欄)
```

### iostat — 磁碟 IO 飽和度

| 寫法 | 作用 |
|---|---|
| `iostat -xz 1` | 擴展統計(`-x`)、隱藏無活動設備(`-z`)、每秒刷 |
| `iostat -xz 1 3` | 刷 3 次後停 |
| `iostat -dx` | 只看磁碟設備 |

看哪幾欄:`await`(單次延遲 ms,**最重要**)、`%util`(繁忙度)、`r/s w/s`(IOPS)。

**⚡ 驗證**:
```bash
iostat -xz 1 2 | tail -15    # 預期:每個磁碟一行;看 await / %util 欄
```

### ⚡ 配角速驗(`uptime` / `nproc` / `mpstat` / `pidstat` / `df` / `dmesg`)

```bash
uptime                  # 預期:結尾 "load average: x.xx, x.xx, x.xx"
nproc                   # 預期:核心數(拿來除 load)
mpstat -P ALL 1 1       # 預期:每顆核一行 + all 匯總
pidstat 1 1             # 預期:各進程 %usr / %system
df -h /                 # 預期:根分區空間使用率
df -i /                 # 預期:根分區 inode 使用率
dmesg -T 2>/dev/null | grep -i oom | tail   # 預期:通常無輸出(容器內 dmesg 可能權限不足,需 --privileged 或主機跑)
```

---

## 深挖

- 記憶體模型、虛擬記憶體 / RSS / swap 的原理 → **`linux-handson/04-memory-model`**
- 完整的線上排查流程(從現象到根因) → **`linux-handson/07-troubleshooting-playbook`**
- 進程狀態 `R/S/D/Z`、為什麼 `D` 殺不掉 → **`01 進程與作業控制`**
- 這些資源瓶頸如何反推架構決策(容量規劃) → **`os-for-architects`**
