# 第 5 章 · Vertical Slice + 按功能 vs 按層(H2 · 檔案怎麼擺)

> 🔬 `04` 決定了「依賴往哪指」,這章決定一個更具體、天天遇到的問題:**package / 目錄到底怎麼分**。同樣是 Clean 架構,檔案可以**按技術層**擺(controllers/ services/ repositories/),也可以**按業務功能**擺(order/ payment/ inventory/)——選錯,改一個需求就要在五個目錄間來回跳。
>
> **最常見的露怯**:① 默認「按層分包」是唯一方式,從沒想過按功能;② 頂層目錄全是 `controller/service/dao`,**一眼看不出這是什麼業務系統**;③ 不知道「一個限界上下文 = 一個模塊」怎麼落到目錄上。這章把兩種組織法、Vertical Slice、Screaming Architecture 講清。

---

## Part A · 兩種分包法

### 按層分包(Package by Layer)— 你最熟的默認
```
com.shop
├── controller/   OrderController, PaymentController, InventoryController
├── service/      OrderService, PaymentService, InventoryService
├── repository/   OrderRepository, PaymentRepository, InventoryRepository
└── model/        Order, Payment, Inventory
```
**問題(霰彈式修改 / shotgun surgery)** 🔬:加一個「訂單退款」功能,要動 `controller/`、`service/`、`repository/`、`model/` **四個目錄**。一個功能的代碼**散落四處**,而四處的代碼**互不相關**(OrderController 和 PaymentController 放一起,只因為都是 controller)。**低內聚、高耦合的目錄。**

### 按功能分包(Package by Feature)
```
com.shop
├── order/        OrderController, OrderService, Order, OrderRepository
├── payment/      PaymentController, PaymentService, Payment, PaymentRepository
└── inventory/    InventoryController, ...
```
**好處**:一個功能的代碼**全在一個包**;改訂單只動 `order/`;`order/` 高內聚,包與包之間低耦合;**刪一個功能 = 刪一個包**。

> 一句話:**按層分包按「技術角色」歸類,按功能分包按「業務能力」歸類。** 後者讓「一起改的東西放一起」,這正是高內聚。

---

## Part B · Screaming Architecture:目錄該「喊出」業務

Uncle Bob 的提法:看一個項目的頂層目錄,**它應該喊出「我是什麼業務系統」,而不是「我用什麼框架」**。

```
❌ 看到 controllers/ services/ repositories/  →「這是個 Spring 項目」(框架喊話)
✅ 看到 order/ payment/ inventory/ shipping/  →「這是個電商系統」(業務喊話)
```

> 🔬 洞察:框架是**細節**(`04` 的最外圈,可替換),業務才是**核心**。目錄結構應該反映核心而非細節。一個健康的 codebase,新人掃一眼頂層目錄就懂業務地圖——這也呼應 `01` 的限界上下文:**頂層目錄 ≈ 你的上下文地圖**。

---

## Part C · Vertical Slice Architecture:把「切片」推到極致

按功能分包再進一步,就是 **Vertical Slice(垂直切片)**:**每個功能是一條從入口到 DB 穿透所有層的獨立切片**,切片之間盡量不共享。

```
傳統水平層:  ─── Controller 層 ───
             ─── Service 層 ───      ← 一個功能橫跨所有水平層(到處改)
             ─── Repository 層 ───

垂直切片:    │下單│退款│查詢│  ← 每個功能是一條豎切片,自帶它需要的全部
             │ ↕ │ ↕ │ ↕ │     各切片獨立,改一個不碰另一個
```

**特點**:
- 每個切片 = 一個 use case,自帶它的 request/handler/響應,**只引入它真正需要的東西**(查詢切片可能直接 SQL,不必走完整聚合)。
- 常配 **CQRS(`06`)+ 一個 handler per request**(如 .NET 的 MediatR、Java 的 command/query handler)。
- **針對性建模**:寫操作走完整領域模型(聚合),讀操作走輕量查詢——不強求所有切片用同一套模型。

| | Vertical Slice 的取捨 |
|---|---|
| ✅ 好處 | 高內聚、改動局部化、每個切片可按需簡繁、好刪除 |
| ⚠️ 代價 | 切片間若有共性,可能有重複;需紀律避免「切片裡又長出小單體」 |

> 🔬 和分層不是對立:你仍可在切片**內部**用 Clean/依賴反轉。Vertical Slice 管「**橫向怎麼切**(按功能)」,分層管「**縱向依賴方向**」——兩個維度。

---

## Part D · 落地:限界上下文 → 模塊 → 包

把前面幾章接起來,得到一套完整的目錄主張:

```
com.shop
├── order/          ← 限界上下文(01)= 模塊 = 頂層包
│   ├── domain/         聚合 Order、VO Money、OrderRepository 接口(02/04)
│   ├── application/    應用服務 / use case handler
│   └── infrastructure/ JpaOrderRepository、對外 ACL(01/04)
├── payment/        ← 另一個限界上下文,結構同上
└── inventory/
```

> **模塊化單體(modular monolith)的精髓**:先用**包/模塊邊界**把限界上下文隔開(`order` 不准直接 import `payment.domain`,只能透過其對外接口/事件),**扛不住再把某個包拆成獨立服務**——拆分成本極低,因為邊界早就劃好了。這就是 `01`「先模塊邊界、再拆服務」在目錄上的兌現。

**生態**:
- **Go**:強烈偏好**按功能分包**(package = 一個能力),`internal/order`、`internal/payment`;按層分包在 Go 裡很少見、被視為反慣例。
- **Java/Spring**:歷史上多按層(教程帶壞的),但社區早已轉向按功能 / 模塊化(Spring Modulith 就是幹這個)。
- **Python**:按功能分模塊(`order/`、`payment/`)同樣是主流好品味。

---

## 面試滿分答法

> **Q:「你怎麼組織項目的包結構?」**
> 「**按業務功能,不按技術層。** 頂層是 `order/ payment/ inventory/` 這種業務模塊(一個 ≈ 一個限界上下文),不是 `controller/ service/ dao/`。理由:① 一個功能的代碼全在一個包,改動局部化,避免霰彈式修改;② 頂層目錄一眼喊出業務(Screaming Architecture);③ 模塊邊界劃好了,將來要拆微服務成本極低。包**內部**再用依賴反轉保持領域純淨。」

---

## 本章小結

- **按層分包**(controller/service/dao)= 按技術角色歸類 → **霰彈式修改、低內聚**;**按功能分包**(order/payment)= 按業務能力歸類 → 高內聚、改動局部、好刪除。
- **Screaming Architecture**:頂層目錄該喊出業務(電商系統)而非框架(Spring 項目);框架是細節,業務是核心。
- **Vertical Slice**:每個功能是穿透所有層的獨立切片,可按需簡繁、常配 CQRS;管「橫向怎麼切」,和分層的「縱向依賴」是兩個維度,可疊加。
- **落地**:限界上下文 = 模塊 = 頂層包;模塊化單體先用包邊界隔離,扛不住再拆服務(`01` 的兌現)。Go 天生按功能,Java/Python 社區也已轉向。
- 下一章 `06`:**CQRS(設計面)**——Vertical Slice 常配的讀寫分離,在 code 層到底怎麼回事、和資料庫主從有什麼不同。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 按層分包和按功能分包,各按什麼維度歸類?為什麼前者導致「霰彈式修改」?
2. 「霰彈式修改」具體是什麼體驗?按功能分包怎麼解?
3. Screaming Architecture 在主張什麼?為什麼說框架是細節、業務是核心?
4. Vertical Slice 是什麼?它和「分層」是對立的嗎?兩者各管哪個維度?
5. Vertical Slice 的好處和代價各是什麼?它常和什麼模式搭配?
6. 「限界上下文 → 模塊 → 包」怎麼對應?模塊化單體為什麼能讓「將來拆服務」變便宜?
7. Go 和 Java 在分包習慣上的差異是什麼?
8. **面試題**:「你怎麼組織項目包結構?」給出按功能分包的三點理由。
