# 第 0 章前傳 · 記憶體模型:從 JMM 到分布式一致性

> 🔬 大部分人是把 JMM 當「Java 八股」背下來的:原子性、可見性、有序性,volatile、synchronized,講完收工。於是它變成一個**孤立的知識點**——記得住,串不起來。
>
> 本章要證明的事只有一件:**JMM、事務隔離級別、分布式一致性模型,是同一個問題在三個尺度上的化身。** 而且它們不是「像」,是**同源**——`happens-before` 這個詞是 Lamport 1978 講分布式系統時發明的,而「線性一致性」原本是講多處理器共享記憶體的。這兩個領域一直在互相抄作業。
>
> JMM 的特殊價值在於:它是這條線上**唯一一個你能在自己機器上、用幾行代碼、看到指令級證據**的尺度。往上到 MVCC、到分布式,就再也沒有這麼直接的實錘了。

## 本章定位

- **放在第 0 章之前**:它不講分布式,它講的是「為什麼會有一致性問題」這件事本身。讀完再進 `00-理論基礎-CAP與共識`,CAP 的 C 會有觸感。
- **不是 Java 教程**。Java 只是切入點(對多數後端工程師,這是最省力的入口);Part B 會證明它跟 Java 沒關係。
- **讀完你要能回答**:為什麼每個語言都得有記憶體模型?happens-before 到底保證什麼(不保證什麼)?volatile 在你的 ARM Mac 上編譯成哪條指令?為什麼 Outbox 是分布式版的 memory barrier?

返回索引:[生產級分布式系統 L0–L9 master 索引](./README.md)。

---

# Part A · 兩條收口軸(先給地圖)

如果 JMM 對你是散的,大概率是缺這兩條軸。它們**橫跨三層都成立**,是本章真正的骨架。

## 軸一:單物件免費,多物件要合約

這是最關鍵、也最少被講清楚的區分。兩個概念長得像,是兩回事:

- **快取一致性(Cache Coherence,MESI 那套)**:對**同一個**記憶體位址,所有 CPU 核看到的寫入順序一致。**硬體免費給你的。**
- **記憶體一致性 / 記憶體模型(Memory Consistency)**:**不同**位址的操作之間,允許怎麼重排。**MESI 完全不管這件事。** 這才是 JMM 在管的。

很多人把這兩個混成一個「快取一致性」,於是永遠想不通:「既然快取都一致了,為什麼還要 volatile?」

> **答案:快取一致管的是單個變數,記憶體模型管的是變數之間的順序。**

同一條軸往上長,三層完全同構:

| 層 | 單物件(免費 / 容易) | 多物件(要合約) |
|---|---|---|
| **CPU** | MESI 保證單一 cache line 一致 | 記憶體模型 / memory barrier |
| **DB** | 單行 UPDATE 天然原子 | 跨行跨表 → 需要**事務** |
| **分布式** | 單 key 線性一致(Raft 單 log、Redis 單執行緒) | 跨 key → **分布式事務難**;Redis Cluster 不支援跨 slot 事務 |

**「跨物件才需要合約」這一句,把三層全串起來了。** 讀後面任何一章,都可以先問:這章在講單物件還是多物件?

## 軸二:三層在問同一句話

> **「A 做了兩件事,B 能看到什麼組合?」**

| 尺度 | 具體提問 | 答案 |
|---|---|---|
| **JMM** | A 執行緒 `data = 42; flag = true;` — B 看到 `flag == true` 時,`data` 一定是 42 嗎? | **不一定**,要 volatile |
| **事務隔離** | A 事務改了兩行 — B 事務會看到「只改了一行」的中間態嗎? | **看隔離級別** |
| **分布式** | A 服務先寫訂單、再發 MQ — 消費者收到消息時,回查 DB 查得到訂單嗎? | **不一定** |

第三個是最經典的生產 bug:**「消費者收到消息了,回頭查庫查不到」**。它就是分布式版本的「忘了加 volatile」——兩個寫入(DB、MQ)之間沒有順序保證,觀察者看到了後一個卻看不到前一個。

> **Outbox 模式的本質,就是分布式尺度的 memory barrier。**
> 把「寫業務」和「寫消息」塞進同一個本地事務,強制它們對外只能一起可見——跟 volatile 寫強制刷 store buffer、禁止重排,是完全同一件事的不同尺度。
> 一個發生在 3 奈秒的 store buffer 裡,一個發生在 30 毫秒的網路上。

---

# Part B · 記憶體模型不是 Java 特有的

## 為什麼是 Java 第一個做?因為它承諾跨平台

**任何有多執行緒 + 共享記憶體的語言都必須有記憶體模型**,區別只在「寫進規範了沒」。

Java 第一個做,是因果不是巧合:**它承諾 write once, run anywhere**。同一份 bytecode 要在 x86、SPARC、PowerPC 上跑出一樣的行為——那你就**不能**說「重排序看平台」。C 可以耍賴(「這是實現定義行為」),Java 不能,因為跨平台就是它的賣點。

而且 **Java 第一版(1995 JLS)的記憶體模型是有缺陷的**,到 **JSR-133(Java 5,2004)** 才修好。修的過程中才給了 `volatile` 今天的語義(在那之前,volatile 不保證與普通變數之間的 happens-before),也才補上 `final` 欄位的安全發布保證。

**C++ 是看著 Java 踩完坑,2011 年才做的**(理論基礎是 Boehm & Adve, PLDI 2008)。中文面試圈把記憶體模型當「Java 知識點」,純粹是因為 Java 先行了七年。

## 跨語言對照:差異幾乎全在「反面條款」

每個記憶體模型都由兩半條款組成:

- **正面條款**:列舉哪些操作之間**有** happens-before 邊。你用這些原語 → 你得到保證。
- **反面條款**:沒有 happens-before 邊,卻同時訪問同一位址、至少一個是寫 → 這叫 **data race**,然後規範規定「這時候會發生什麼」。

**語言之間的差別,幾乎全在反面條款:**

| 語言 | 記憶體模型 | 同步原語 | data race 發生時 |
|---|---|---|---|
| **Java**(JSR-133, 2004) | 有,happens-before | `volatile` / `synchronized` / `final` / `Atomic*` | 定義得最保守:結果任意,**但不會憑空出現值**(no out-of-thin-air)。程式仍在規範內,記憶體不會損壞——因為 Java 必須保證沙箱安全 |
| **C++11** | 有,happens-before + 6 種 `memory_order` | `std::atomic<T>` / `mutex` | **UB**。編譯器可以假設 race 不存在並據此優化:刪掉你的 null 檢查、把有限循環變無限循環。**整個程式失去意義**,不只是那個變數出錯 |
| **Go**(2014,2022 大改) | 有,happens-before | channel / `sync.Mutex` / `sync/atomic` / `once.Do` | 中間路線。不採用 C++ 的全域 UB(記憶體安全不被破壞),但明確承認:racy 程式可讀到**撕裂值**(torn read,多字結構如 interface、slice header 讀到一半舊一半新),也可能直接崩潰 |
| **Rust** | **直接沿用 C++11 的模型** | `Arc<Mutex<T>>` / `Atomic*` + `Ordering` | 編譯期就不讓你寫出來(所有權 + `Send`/`Sync`);要寫得先打 `unsafe` |
| **Python (CPython)** | **沒有正式規範**,靠 GIL 提供事實保證 | GIL + `threading.Lock` | GIL 讓你大部分時候矇對,但 `i += 1` 仍不原子(LOAD/ADD/STORE 三條 bytecode,中間可切換) |
| **C / C++98 以前** | **沒有** | 平台相關(pthread) | 靠運氣 + `volatile` 迷信 |

三個值得單獨記的點:

1. **Rust 不是換了模型**,它用的就是 C++11 那套。它做的是「在型別系統層面不讓你走進需要記憶體模型的危險區」。
2. **Go 官方文檔那句名言**——這是理解 Go 那一格的鑰匙:
   > *If you must read the rest of this document to understand the behavior of your program, you are being too clever. Don't be clever.*
   >
   > 意思是:這份規範是寫給編譯器實現者和寫 `sync` 套件的人看的。**應用層如果需要靠讀它來確認自己代碼對不對,那代碼本身就寫錯了**——該用 channel 或 mutex。
3. **Python 這條對後端轉型特別重要**:GIL 給的是假安全感。而 **3.13 起有實驗性 free-threaded build(PEP 703,無 GIL),3.14 轉為正式支援**——GIL 一拿掉,Python 就需要一個真正的記憶體模型,這是現在進行式。

## 硬體那一側:x86 和 ARM 真的不一樣

記憶體模型之所以必要,根源在硬體:

| 架構 | 記憶體序 | 允許什麼重排 |
|---|---|---|
| **x86 / x64** | **TSO**(Total Store Order,相對強) | 基本只允許 **StoreLoad** 重排(store buffer 造成) |
| **ARM64 / RISC-V / POWER** | **弱序** | 幾乎什麼都能重排 |

**後果**:同一段沒加同步的代碼,在 x86 上跑一萬次全對,換到 ARM 伺服器上就掛。這不是理論——現在的 Apple Silicon 和多數雲廠商的 ARM 實例都是弱序機器。

> **硬實錘**:Apple 為了讓 Rosetta 2 翻譯 x86 代碼不出錯,**在 M 系列晶片裡專門加了一個 TSO 開關**。硬體廠商願意為此改矽片,就說明這個差異是真的、而且會咬人。

---

# Part C · happens-before 到底是什麼 🔬

這是全章最容易理解錯的地方。先修三個常見誤解。

## 誤解 ①:「字節碼重排序」——層級錯了,而且這正是關鍵

`javac` 幾乎不做重排序,字節碼基本是源碼的忠實翻譯。真正重排的是:

1. **JIT 編譯器(C1/C2)**——主力
2. **CPU 亂序執行 + store buffer**——硬體層

**這一點直接證明了 Part B**:如果重排發生在字節碼層,它確實會是 Java 特有的。但它發生在 JIT 和 CPU 層——C++、Go、Rust 沒有字節碼,**一樣被重排**。這就是為什麼每個語言都得有記憶體模型。

**最經典的實錘:雙重檢查鎖(DCL)單例**

```java
if (instance == null) {
    synchronized (Foo.class) {
        if (instance == null) instance = new Foo();  // ← 這行不是原子的
    }
}
```

`new Foo()` 其實是三步:①分配記憶體 ②跑構造器 ③把引用賦給 `instance`。**②③ 可以被 JIT 重排**。另一個執行緒在最外層 `if` 看到 `instance != null`(**根本沒進鎖**),拿到一個構造器還沒跑完的物件。

所以 `instance` 必須宣告成 `volatile`。**注意:字節碼裡這三步是清清楚楚分開寫著的,重排是 JIT 幹的。**

## 誤解 ②:happens-before 不是「執行順序」,是「可見性契約」

`A happens-before B` **不代表** A 在時間上先執行。它代表:

> **如果 A hb B,那 B 保證看得見 A 的所有寫入。**

JVM/CPU **仍然可以重排** hb 關係內的指令——只要沒人能觀測出來。happens-before 規定的是**你被允許觀測到什麼**,不是機器實際怎麼跑。

而且它是**偏序(partial order)**——絕大多數操作對之間**根本沒有** hb 關係。沒關係 = data race = 什麼都可能發生。

> 重點不是「有些地方需要保證順序」,而是:**預設全部無序,你得手動一條一條把邊建起來。**

## 誤解 ③:它不是「引申出來的隱藏特性」,它是地基

方向反了。規範是**先定義 happens-before 這個關係**,然後用它來**定義每個同步原語是什麼**:

- 「對某個 monitor 的 unlock,happens-before 後續對同一個 monitor 的 lock」 ← 這**就是** `synchronized` 的記憶體語義定義
- 「對 volatile 變數的寫,happens-before 後續對同一變數的讀」 ← 這**就是** `volatile` 的定義

**語法的含義是用 happens-before 定義的,不是反過來。**

## 引擎:傳遞性

A hb B,B hb C ⟹ A hb C。整台機器就是這條傳遞律:

```java
// 執行緒 1
data = 42;          // (1) 普通寫,data 不是 volatile
flag = true;        // (2) volatile 寫

// 執行緒 2
if (flag) {         // (3) volatile 讀
    use(data);      // (4) 保證讀到 42
}
```

| 邊 | 來源 |
|---|---|
| (1) hb (2) | 同執行緒內的程序順序 |
| (2) hb (3) | **volatile 寫 hb 後續 volatile 讀** ← 唯一一條跨執行緒的邊 |
| (3) hb (4) | 程序順序 |
| ⟹ **(1) hb (4)** | **傳遞性** |

**關鍵:`data` 根本不是 volatile。** 那一個 volatile 變數像一道閘門,把它之前的所有普通寫「馱」了過去。這叫**安全發布(safe publication)**。

由此推出一個極易踩的坑:

> **volatile 不是「給一個變數套保護罩」,而是「在訪問這個變數的那個時間點上,攔一道柵欄」。柵欄攔的是整條指令流,不是那個變數。**
>
> 所以**只在寫端用 volatile 是沒用的**。你只立了出口的柵欄;讀端如果讀的是普通變數,那一側沒有屏障,照樣能把 `use(data)` 提前。**happens-before 是兩個執行緒之間的關係,不是單個變數的屬性——兩側都得有。**

---

# Part D · release / acquire:為什麼取這兩個名字 🔬

這組名字讓很多人卡住,是因為**它不是從「讀寫」來的,是從「鎖」來的**。

## 詞源:就是 lock 的那兩個動作

```java
lock.acquire();   // 取得鎖
   ...
lock.release();   // 釋放鎖
```

人們先發現「鎖」除了互斥之外,還順帶提供了記憶體可見性保證。而且**進門和出門的保證不一樣**:

- **acquire(進門)**:我拿到鎖了 → 上一個持鎖者在 release 之前做的一切,我必須看得見。
- **release(出門)**:我要放鎖了 → 我在臨界區裡做的一切,必須讓下一個 acquire 的人看得見。

後來(**Gharachorloo 等人 1990 年 Stanford DASH 的 Release Consistency 論文**)把這兩個保證從鎖裡**抽出來**,變成可以單獨貼在任何原子操作上的標籤——名字就照抄了鎖的動作。C++11 直接沿用。

所以它的語義核心是**交接棒**,不是「讀」和「寫」:

- **release = 交棒**:交出去之前,我的活必須全部幹完
- **acquire = 接棒**:接到棒之後,我才能開始幹活

(常見的說法「release 是寫端、acquire 是讀端」講的是**結果**,不是**意思**——交棒的那頭通常在寫,接棒的那頭通常在讀。難怪繞。)

## 關鍵:它們是方向相反的**半扇門**

這才是為什麼需要兩個名字,而不是一個「屏障」。

```
   普通操作 A
   普通操作 B
   ══════════ release ══════════   ← A、B 不准掉到線下面
   普通操作 C                        (但 C 可以浮到線上面,允許!)
```

```
   普通操作 X                        (X 可以掉到線下面,允許!)
   ══════════ acquire ══════════   ← Y、Z 不准浮到線上面
   普通操作 Y
   普通操作 Z
```

兩個都只擋**一個方向**,術語叫**半透屏障(one-way / semi-permeable barrier)**:

- release 擋「往下漏」
- acquire 擋「往上漏」

**合起來,正好圍出一個「只進不出」的袋子:**

```
        ↓ 外面的可以掉進來(無害)
   ═════════ acquire ═════════
        ✗ 裡面的浮不出去
          臨 界 區
        ✗ 裡面的掉不出去
   ═════════ release ═════════
        ↑ 外面的可以浮進來(無害)
```

這個不對稱不是隨便定的——它**精確地對應「臨界區可以被收窄,但絕不能洩漏」**:外面的代碼跑進臨界區裡執行,最多損失一點並發度,正確性沒問題;裡面的代碼跑到外面去,互斥就破了。

> **名字之所以是一對而不是一個,是因為門是單向的,需要一上一下兩扇才能關住一個區間。**

順帶解釋了為什麼 `seq_cst` 更貴:它是**雙向全擋的完整屏障**,兩個方向都不准過。

## 換個比喻:出貨 / 收貨

- **release = 出貨**:貨必須先裝好箱,才能貼「已出貨」標籤。標籤絕不能比貨先出去。
- **acquire = 收貨**:看到「已出貨」標籤,才能開箱。開箱動作絕不能比看標籤先做。

回到那個例子:

```java
data = 42;        // 裝箱
flag = true;      // 貼標籤 ← release:標籤不准跑到裝箱前面

if (flag)         // 看標籤 ← acquire:開箱不准跑到看標籤前面
    use(data);    // 開箱
```

標籤先出去而貨還沒裝 = **release 屏障缺失**;沒看標籤就開箱 = **acquire 屏障缺失**。兩邊各缺一個都會出事。

## 跨語言:同一條邊,四種穿著

| | release 端 | acquire 端 |
|---|---|---|
| **Java** | `volatile` 寫、`unlock` | `volatile` 讀、`lock` |
| **Go** | `ch <- v`、`close(ch)`、`mu.Unlock()` | `<-ch`、`mu.Lock()` |
| **C++** | `store(memory_order_release)` | `load(memory_order_acquire)` |
| **Rust** | `Ordering::Release` | `Ordering::Acquire` |

同一個安全發布模式:

```java
data = 42; flag = true;                 // Java:flag 宣告為 volatile
```
```go
data = 42; close(ch)                    // Go:另一端 <-ch 之後讀 data
```
```cpp
data = 42; flag.store(true, release);   // C++:另一端 load(acquire)
```

**完全同一條 happens-before 邊。** C++ 只是把 Java 藏起來的旋鈕暴露出來讓你手調。

## 注意:這兩個詞在 Java 裡本來不存在

**Java 的 API 從來沒用過這兩個詞。** Java 只給你 `volatile`(永遠是最強的 `seq_cst`,不讓你選),所以 Java 程式員原本不需要這套詞彙。

release/acquire 是 **C++11 帶進主流**的。Java 到 **9** 才在 `VarHandle` 上補了 `setRelease()` / `getAcquire()`(在那之前只有 `AtomicInteger.lazySet()` 這個名字取得很爛的 release 語義方法)。

> 拿它當跨語言通用語,是因為它目前是唯一一套能同時描述 Java / Go / C++ / Rust 的詞彙。但對 Java 直覺來說它是外來語——**腦子裡永遠翻譯成「出門 / 進門」,語義完全等價。**

---

# Part E · 底層實現:JIT 到底發了什麼指令 🔬

前面講的都是契約。這節講機器。

## 先拆一個常見誤會

`volatile` 只寫在**欄位宣告**上:

```java
class Holder {
    int data;                    // 普通欄位
    volatile boolean flag;       // volatile 欄位
}
```

它的含義是:**這個欄位的每一次讀、每一次寫,不管出現在代碼的哪裡,JIT 都要在那個點插入記憶體屏障。**

所以 `data = 42; flag = true;` 不是「實現」,它是**一次使用**。屏障是在 `flag = true` 被編譯成機器碼時、由 JIT 插進去的。

## 中間層:JSR-133 的四種抽象屏障

JIT 不是直接想到具體指令的。規範(Doug Lea 的 JSR-133 Cookbook)定義了四種抽象屏障,JIT 再按目標架構翻譯:

`LoadLoad` / `LoadStore` / `StoreStore` / `StoreLoad`(最貴的一種)

volatile 的規則:

```
    data = 42;              ← 普通寫
    [StoreStore 屏障]        ← 保證 data 先落地
    flag = true;            ← volatile 寫
    [StoreLoad 屏障]         ← 最貴那條
```

```
    if (flag)               ← volatile 讀
    [LoadLoad + LoadStore]   ← 保證後面的讀不會被提前
        use(data);          ← 普通讀
```

## 真正落到指令:x86 和 ARM 完全不同

| | volatile **讀** | volatile **寫** |
|---|---|---|
| **x86 / x64**(TSO) | 就是一條普通 `mov`,**零額外指令** | `mov` + `lock addl $0, (%rsp)` |
| **ARM64**(弱序) | `ldar`(load-acquire 指令) | `stlr`(store-release 指令) |

幾個要點:

- **x86 上 volatile 讀完全免費**——一條指令都不多。因為 TSO 本來就不允許讀被重排到讀之後,JIT 只要自己別重排就行。對照上面的抽象屏障:`StoreStore` / `LoadLoad` / `LoadStore` 這三種 x86 硬體天然保證,翻譯成**零指令**;只有 `StoreLoad` 要真的發指令。
- **x86 上 volatile 寫要花錢**,約幾十個 cycle。HotSpot 用 `lock addl $0,(%rsp)`(對堆疊頂加 0,等於什麼也沒做)而不是 `mfence`,純粹因為前者更快。
- **ARM 上讀寫都要花錢**,弱序架構什麼都不保證,得用專門的 acquire/release 指令。

**同一份 Java 代碼,在 x86 上 volatile 讀免費、在 ARM 上要付費——記憶體模型讓你不用管這個差異,代價由 JIT 承擔。這就是「跨平台」的具體含義。**

## 代價對比:Java 為什麼比 C++ 貴

在 x86 上,C++ 的 `store(release)` 編譯成**一條普通 `mov`,零額外指令**——因為 release 語義 TSO 天然滿足。而 Java 的 `volatile` 寫等價於 `seq_cst`(最強那檔),必須付 `lock addl`。

> 同樣是安全發布:**C++ 可以選 release 花 0,Java 只能用 volatile 花幾十 cycle。**
> Java 用「少一個決策」換「永遠不會選錯」——這是個明確的設計取捨,不是缺陷。

## Go 的實現路徑不一樣

Go 的 `close(ch)` / `<-ch` **不是編譯器插屏障,是進 runtime 函式**。channel 內部有 `mutex` 和 `sync/atomic` 操作,最終還是落到同樣的 acquire/release 指令上——只是包了三層。

**所以 channel 比 volatile 貴得多,但語義更清楚。** 這也呼應 Go 那句「Don't be clever」:它刻意讓你用貴但不會錯的東西。

## 親手驗證(強烈建議做一次)

在 Apple Silicon 上你能直接看到 `stlr`:

```bash
# 路線 A(推薦):JMH + perfasm
mvn ... -Djmh.args="-prof perfasm"

# 路線 B:直接看 JIT 輸出,需要先裝 hsdis 反組譯庫
java -XX:+UnlockDiagnosticVMOptions -XX:+PrintAssembly ...
```

搜輸出裡的 `stlr`,就是你那行 `flag = true`。把 `volatile` 拿掉再跑一次,指令消失。

> **這是整條學習線上,唯一一個能在幾分鐘內、用自己的機器、親眼看到「抽象契約 → 具體指令」的地方。** 往上到 MVCC、到分布式,就再也看不到這麼直接的證據了。值得花這半小時。

---

# Part F · 三層對照總表

## Java 並發 ↔ DB:最省力的過渡橋

有 Java 底子的人,用這張表讀 `mysql-handson/05-mvcc` 和 `06-locking` 能快一倍:

| Java 並發 | DB 裡的同一件事 |
|---|---|
| `synchronized` / `ReentrantLock` | `SELECT ... FOR UPDATE`(悲觀鎖) |
| `AtomicLong.incrementAndGet()` | `UPDATE t SET n = n + 1 WHERE id = ?`(單條 SQL 原子) |
| CAS 重試迴圈 | 樂觀鎖 `UPDATE ... WHERE version = ?` |
| **`i++` 不原子,`volatile` 救不了** | **lost update**(讀-改-寫丟更新) |
| 執行緒讀到的本地快照 | **ReadView**(MVCC 快照讀) |
| 死鎖 + 等待圖檢測 | InnoDB 死鎖檢測(也是等待圖,挑改動量小的當犧牲者回滾) |

> `volatile` 那條特別值得記:**可見性 ≠ 原子性**。這個坑在 DB 裡叫「讀已提交也還是會丟更新」,在分布式裡叫「消息送到了不代表業務做了」。**同一個坑,三個名字。**

## 三特性的逐層對映

| | **JMM**(執行緒 ↔ CPU 核) | **單機事務**(事務 ↔ DB) | **分布式**(節點 ↔ 副本) |
|---|---|---|---|
| **原子性** | 一組操作不可分割<br>`synchronized` / CAS | ACID 的 A:全成或全敗<br>**+ 可回滾**(undo log) | **沒有**跨服務原子性<br>→ 所以才有 Saga / TCC |
| **可見性** | 寫了別人看不看得到<br>`volatile` → 刷 store buffer | 隔離級別:誰看得見未提交 / 已提交<br>MVCC ReadView | 副本可見性契約<br>線性一致 / 因果 / 最終一致 |
| **有序性** | 編譯器 + CPU 重排序<br>→ happens-before | 可串行化 = 存在等價串行順序 | 全序 / 因果序<br>Lamport 時鐘、共識定 log 順序 |

**共同的物理成因**:三層都是「為了性能加了緩衝(store buffer / buffer pool / 消息隊列 / 副本),緩衝打破了『單一全局狀態、按序執行』的幻覺,只好造一套契約,規定你在哪些點上可以把幻覺買回來、代價是什麼」。

## 三個必須斷開的地方(別過度類比)

1. **JMM 沒有回滾。** JMM 的原子性 = 不可分割(靠排他實現);事務的 A = 全成或全敗**且能回滾**(靠 undo log 實現)。機制完全不同。把回滾搬進記憶體的嘗試叫 STM(軟體事務記憶體),基本沒進主流。
2. **JMM 沒有 D(持久性)。** 持久性在記憶體模型裡沒有對應物,redo log / fsync 那一層在 JMM 之外。
3. **JMM 沒有部分失敗(partial failure)。** 執行緒不會「持著鎖單獨死掉」——JVM 掛了大家一起掛,鎖跟著消失。分布式裡持鎖節點掛了**鎖還在**,所以才需要 lease/TTL,所以 Redlock 才有爭議,所以才需要對帳。

> **第 3 點是單機並發和分布式的本質分野。** 讀 `11-並發正確性與長任務協調` 那條推理鏈時,「故障模型」那一格填的就是這個——在 JMM 裡它是空的。

## 一個面試能加分的硬點

很多人以為「可串行化 = 最強一致」,錯:

| 概念 | 層面 | 保證什麼 |
|---|---|---|
| **Serializability** | 事務層(多操作) | 存在某個等價的**串行順序**,**不管實時性** |
| **Linearizability** | 單物件層(單操作) | 尊重**實時順序** |
| **Strict Serializability** | 兩者合體 | Spanner 的 external consistency 就是這個 |

一個「永遠回舊快照」的系統也可以是 serializable。這正好對應 JMM:`volatile` 給你的是單變數的線性一致,`synchronized` 給你的是一個區塊的串行化——**兩件不同的事**。

---

## 交叉引用

- **線性一致 / 順序一致 / 因果一致的完整光譜** → [`02-一致性模型與時鐘`](./02-一致性模型與時鐘.md)(Lamport 的 happens-before 在那裡是分布式版本)
- **CAP 的 C = 線性一致** → [`00-理論基礎-CAP與共識`](./00-理論基礎-CAP與共識.md)
- **invariant → 邊界 → 故障模型 → 機制** 的完整推理鏈 → [`11-並發正確性與長任務協調`](./11-並發正確性與長任務協調.md)
- **單機事務的物理真相**(MVCC / 鎖 / redo-undo-binlog,含實機 scenario)→ `mysql-handson/05`、`06`、`07`
- **Outbox 作為分布式 barrier 的完整落地** → `financial-consistency/05-patterns/02-outbox-local-message-table.md`
- **Java 側原語細節** → `java/concurrent/`(`JMM.md`、`synchronized.md`、`AQS.md`、`内存屏障-2种-处理器-JVM-volatile.md`)
- **Go 側同一套東西** → `golang/concurrency/06-sync-memory-model/`

---

## 本章小結

- **記憶體模型不是 Java 特有的**。每個有多執行緒的語言都必須有;Java 只是第一個寫進規範的,因為「跨平台」逼它不能耍賴。差異幾乎全在**反面條款**(data race 時會怎樣):Java 保守、C++ 是 UB、Go 允許撕裂值、Rust 編譯期禁止。
- **軸一:單物件免費,多物件要合約。** 快取一致性(MESI)管單個位址,記憶體模型管**位址之間的順序**——這兩個不是一回事。同構往上:單行 vs 事務、單 key vs 分布式事務。
- **軸二:三層在問同一句話**——「A 做了兩件事,B 能看到什麼組合?」`volatile` 缺失 / 隔離級別 / 「收到消息但查不到庫」是同一個問題的三個尺度。**Outbox 就是分布式版的 memory barrier。**
- **happens-before 不是執行順序,是可見性契約**;它是**偏序**(預設無序,邊要手動建);它是**地基**而非引申——同步原語是用它定義的。**傳遞性**是引擎,所以一個 volatile 能馱著一堆普通寫過河(safe publication)。
- **release/acquire 的名字來自 lock 的兩個動作**,語義是**交接棒**。它們是**方向相反的半透屏障**,合起來圍出一個「只進不出」的臨界區——這就是為什麼要兩個名字。
- **底層實現**:volatile 宣告在欄位上,但屏障插在**每個訪問點**。x86 上 volatile 讀零指令、寫是 `lock addl`;ARM 上是 `ldar`/`stlr`。Java 的 volatile 永遠是 `seq_cst`,所以比 C++ 的 release 貴——用「少一個決策」換「不會選錯」。
- **三個不能類比的地方**:JMM 沒有回滾、沒有持久性、**沒有部分失敗**。最後一個是單機並發與分布式的本質分野。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 「快取一致性(MESI)」和「記憶體模型」差在哪?為什麼快取一致了還需要 volatile?
2. 為什麼是 Java 第一個把記憶體模型寫進語言規範?說出那個因果關係。
3. C++ 的 data race 和 Java 的 data race,後果有什麼本質差別?為什麼 Java 不能學 C++ 那樣定義成 UB?
4. Go 記憶體模型文檔那句「Don't be clever」在講什麼?它針對的讀者是誰?
5. 說出「重排序」發生的兩個真實層級。為什麼**不是**字節碼層?這件事怎麼證明記憶體模型不是 Java 特有的?
6. 用 DCL 單例解釋一次重排序造成的具體 bug:`new Foo()` 拆成哪三步?哪兩步會被換?另一個執行緒會看到什麼?
7. `A happens-before B` 到底保證什麼?它**保證** A 在時間上先執行嗎?
8. 在那個 `data`/`flag` 的例子裡,寫出四條 happens-before 邊,並說明為什麼 `data` 不需要是 volatile。
9. 為什麼「只在寫端加 volatile」是無效的?用一句話說清 happens-before 是誰和誰的關係。
10. release 和 acquire 這兩個名字從哪來?為什麼需要**兩個**名字而不是一個「屏障」?畫出那個「只進不出的袋子」。
11. 為什麼 `seq_cst` 比 release/acquire 貴?從「擋幾個方向」回答。
12. 在 x86 上,volatile 讀要發幾條指令?volatile 寫呢?在 ARM64 上分別是哪兩條指令?為什麼會不同?
13. 同樣做安全發布,C++ 的 `store(release)` 在 x86 上花多少指令?Java 的 volatile 寫呢?Java 為什麼願意付這個差價?
14. 說出 JMM 相對於事務**沒有**的三樣東西。哪一樣是「單機並發」和「分布式」的本質分野?
15. Serializability 和 Linearizability 差在哪?為什麼「可串行化」不等於「最強一致」?
16. **綜合題**:「消費者收到 MQ 消息,回查資料庫卻查不到訂單」——用本章的軸二解釋這個 bug,說明它和「忘了加 volatile」是同一件事,並說出 Outbox 為什麼能修好它。
