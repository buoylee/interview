# 第 2 章 · DDD 戰術設計(H3 · 怎麼正確地充血)

> 🔬 `03` 講了「**決定要充血**」,這章講「**怎麼正確地充血**」。戰術 DDD 的零件不多——Entity、Value Object、Aggregate、Repository、Domain Service、Factory、Domain Event——但**只有一個真正難**:**聚合(Aggregate)的邊界**。其餘都好懂,聚合邊界劃錯,整個領域模型就會出 bug 或鎖死。
>
> **最常見的露怯**:① 把所有概念背得出定義,卻**不會設計聚合邊界**(面試一問「訂單和訂單項該不該在一個聚合?為什麼?」就卡);② 聚合之間直接持有對象引用(該用 ID),導致一加載就拖出半個資料庫;③ 一個事務裡改好幾個聚合(破壞一致性邊界)。這章把零件講清,**重火力全壓在聚合**。

---

## Part A · Entity vs Value Object:有沒有「身份」

戰術建模第一刀:這個概念,**靠身份識別(Entity)**,還是**靠屬性識別(Value Object)**?

| | **Entity 實體** | **Value Object 值對象** |
|---|---|---|
| 怎麼判等 | 靠**唯一 ID**(身份) | 靠**屬性值**(全等才相等) |
| 會變嗎 | 有生命週期、狀態會變 | **不可變(immutable)**,要改就換一個 |
| 例 | 訂單、用戶、賬戶 | 金額 `Money`、地址 `Address`、日期區間 |
| 判斷 | 「換了所有屬性還是同一個嗎?」是→Entity | 「只關心值、不關心是哪一個」→VO |

```java
// Entity:張三改了名字、改了地址,還是同一個張三(靠 id 識別)
class Customer { private final CustomerId id; private String name; /*...*/ }

// Value Object:100 元就是 100 元,不可變;要「改成 120」是 new 一個,不是 setter
record Money(BigDecimal amount, Currency currency) {
    Money add(Money other) { /* 校驗同幣種 */ return new Money(amount.add(other.amount), currency); }
}
```

> 🔬 **為什麼值對象要不可變**:VO 沒有身份,共享出去後若可變,A 改了 B 莫名其妙也變(別名 bug)。**不可變 = 可安全共享、可當哈希鍵、線程安全、好推理**。Java 用 `record`、Go 用值傳遞的 struct、Python 用 `@dataclass(frozen=True)`。**多用 VO 是好品味**:把 `String address`、`BigDecimal amount` 升級成 `Address`、`Money`,類型系統就幫你擋掉一堆錯(幣種不符、地址缺欄)。

---

## Part B · 聚合(Aggregate):戰術 DDD 唯一真正難的點

**定義**:聚合是**一組總是要一起保持一致的對象**,外界只能透過一個入口——**聚合根(Aggregate Root)**——訪問它。

拿訂單:`Order`(根)+ 多個 `OrderLine`(訂單項)+ `Money`、`Address`(VO)。`OrderLine` 不能脫離 `Order` 單獨存在,改訂單項數量必須經過 `Order`。

```java
class Order {                                  // 聚合根
    private final OrderId id;
    private OrderStatus status;
    private final List<OrderLine> lines;       // 內部成員,外界拿不到可變引用
    private Money total;

    void addLine(ProductId p, int qty, Money price) {   // 唯一入口
        if (status != DRAFT) throw new IllegalState("已下單不能加項");
        lines.add(new OrderLine(p, qty, price));
        recalcTotal();                         // 根負責維護「總價 = 各項之和」這個不變量
    }
    // 外界永遠拿不到 List<OrderLine> 的可變引用,只能 order.addLine(...)
}
```

**聚合的三條鐵律(面試重災區)** 🔬:

1. **一致性邊界**:聚合內部的不變量,必須在**一個事務內**始終成立(訂單總價 = 各項之和)。**聚合 = 事務邊界 = 一致性邊界**——一個事務只改**一個**聚合。
2. **聚合間用 ID 引用,不持有對象**:`Order` 裡存 `CustomerId`,**不是** `Customer` 對象。
   > 為什麼?若持有 `Customer` 對象,加載一個訂單會順藤拖出客戶、客戶的訂單……半個庫被拽出來(ORM 的 N+1 / 大對象圖噩夢)。**用 ID 引用,聚合就是個可獨立加載的小單元。**
3. **聚合之間最終一致**:跨聚合的一致性**不能**塞進一個事務(那會鎖死、且違反邊界),改用**領域事件 + 最終一致**(`07`)。例:下單成功後「扣庫存」是另一個聚合的事,發 `OrderPlaced` 事件異步處理。

**怎麼劃聚合邊界(實操心法)**:
- 從**不變量**出發:哪些數據「必須同時正確」?它們在一個聚合。
- **聚合要小**:能小就小。大聚合 = 大事務 = 高併發衝突(樂觀鎖頻繁失敗)。
- 拿不準時,**傾向拆小 + 用 ID 引用 + 最終一致**,而不是塞成一個大聚合。

> 一句話:**聚合是「一致性 + 事務 + 加載」的最小單元;邊界靠不變量劃;聚合間用 ID + 事件 + 最終一致。** 這三句講清,戰術 DDD 的面試就過了。

---

## Part C · Repository:每個聚合根一個

`01`/`04` 出現過的 `Repository`,在戰術層的定位精確化:**Repository 以「聚合」為單位,一個聚合根一個 Repository**,像個「聚合的集合」。

```java
interface OrderRepository {            // 只對聚合根,沒有 OrderLineRepository
    Optional<Order> findById(OrderId id);   // 取出整個聚合(根+成員)
    void save(Order order);                 // 整個聚合一起存
}
```

> 🔬 要點:**不為聚合內部成員建 Repository**(沒有 `OrderLineRepository`)——成員只能透過根訪問,這正是聚合邊界在持久化層的體現。Repository 的接口住領域層、實現住基礎設施層(`04` 依賴反轉)。**它隱藏「存哪、怎麼存」,讓領域層以為自己在操作一個內存集合。**

---

## Part D · Domain Service / Application Service / Factory

剩下幾個零件,各有明確分工——**別把它們和聚合的職責搞混**:

| 零件 | 幹什麼 | 例 |
|---|---|---|
| **Domain Service 領域服務** | 業務邏輯**不屬於任何單一實體**時放這(涉及多個聚合的領域計算) | 轉賬涉及兩個 `Account`、定價涉及多方規則 |
| **Application Service 應用服務** | **編排**,不含業務規則:取聚合 → 調聚合方法 → 存回 → 發事件;管事務、權限 | `04` 那個退化成編排的 `OrderService` |
| **Factory 工廠** | 封裝**複雜的創建**邏輯(創建即需保證不變量時) | 從購物車生成一個合法的初始 `Order` |

**Domain Service vs Application Service(高頻混淆)** 🔬:
- **領域服務有業務規則**,是領域模型的一部分(「轉賬時雙方幣種必須一致」這種規則)。
- **應用服務沒有業務規則**,只做流程編排 + 技術關注點(事務、事務外的權限檢查、發事件)。
- 判據:**「這段邏輯刪掉,業務規則會不會丟?」**會→領域服務;不會(只是流程)→應用服務。

---

## Part E · 生態落地:別把 Java 的重儀式當唯一解

| | Java/C# | Go | Python |
|---|---|---|---|
| Entity/VO | class + `record`/`@Value` | struct(VO 值傳遞) | class + `@dataclass(frozen=True)` |
| 聚合 | 最自然,封裝強 | **常退化**:struct + 一組函數守邊界(`03` 的貧血傾向) | 兩者皆可 |
| Repository | interface + JPA 實現 | interface(使用方定義)+ 實現 | Protocol/ABC + 實現 |

> 🔬 真相:**聚合的「邊界 + 不變量 + 一致性」是 idea,不是 Java 語法**。Go 用「一個 package + 不導出內部字段 + 只導出操作函數」一樣能守住聚合邊界,只是不叫 class。**判據(回扣 `03`):核心域、不變量複雜才值得這套;CRUD 別上。**

---

## 面試滿分答法

> **Q:「訂單和訂單項,該不該放一個聚合?為什麼?」**(直擊聚合設計)
> 「**該**,因為它們有**必須同時成立的不變量**——訂單總價 = 各訂單項金額之和,改任一項都要重算總價,這要求它們在**同一事務、同一一致性邊界**內。所以 `Order` 是聚合根,`OrderLine` 是內部成員,外界只能透過 `order.addLine()` 改,拿不到 `OrderLine` 的直接引用。」

> **Q:「下單要扣庫存,庫存是另一個聚合,怎麼保證一致?」**
> 「**不放一個事務**——那會跨聚合、鎖死、且違反一致性邊界。我讓下單只管自己的聚合,成功後發 `OrderPlaced` 領域事件,庫存聚合異步消費去扣減,**做成最終一致**;失敗用補償(Saga,見 `07`)。一個事務只改一個聚合,是我守的鐵律。」

---

## 本章小結

- **Entity vs VO**:靠身份 vs 靠屬性;**VO 不可變**(可安全共享、類型擋錯),多用 VO 是好品味。
- **聚合(唯一難點)**:一組要一起一致的對象,只能經**聚合根**訪問;三條鐵律——**① 聚合=事務=一致性邊界,一事務改一聚合;② 聚合間用 ID 引用不持對象;③ 聚合間最終一致(事件)**。邊界靠**不變量**劃,**能小就小**。
- **Repository 以聚合為單位**,一根一倉,不為內部成員建倉;接口在領域、實現在基礎設施(依賴反轉)。
- **領域服務(有業務規則,跨多聚合)vs 應用服務(只編排、管事務,無規則)**;Factory 封裝複雜創建。
- 生態:聚合是 idea 不是 Java 語法;Go 用 package 邊界一樣能守;**仍只在核心域值得**。
- 下一章 `05`:**Vertical Slice + 按功能 vs 按層**——這些聚合、服務、Repository 的**檔案到底該怎麼擺**。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. Entity 和 Value Object 的判等方式各是什麼?判斷一個概念是哪種,問哪句話?
2. 值對象為什麼要不可變?不可變帶來哪些好處?
3. 用訂單的例子說清:什麼是聚合、什麼是聚合根?外界怎麼訪問聚合內部?
4. **重點**:聚合的三條鐵律是什麼?「聚合 = 事務邊界 = 一致性邊界」是什麼意思?
5. 為什麼聚合之間要用 ID 引用而不是持有對象?不這麼做會出什麼問題?
6. 跨聚合的一致性怎麼保證?為什麼不能塞進一個事務?
7. 劃聚合邊界的心法是什麼?為什麼「聚合要小」?
8. 為什麼不為聚合內部成員(如 OrderLine)建 Repository?
9. 領域服務和應用服務怎麼區分?判據那句話是什麼?
10. **面試題**:「訂單和訂單項該不該一個聚合」+「下單扣庫存怎麼保證一致」,給出兩段滿分答法。
