# 第 3 章 · 充血 vs 貧血 + Transaction Script + Active Record(H3 · 何時別上 DDD)

> 🔬 前面講的都是「怎麼上 DDD」,這章是**配重**:教戰術 DDD 的**對立方案**,以及最重要的——**什麼時候不該上 DDD**。資深的標誌不是「會用聚合」,是「知道這塊 CRUD 不配上聚合」。
>
> **最常見的露怯**:① 聽說「貧血模型是反模式」就到處鄙視貧血,卻說不清它什麼時候其實是**對的選擇**;② 自己天天在寫 Transaction Script 卻不知道它有名字、是正當模式;③ 把 Active Record 和 Repository 混為一談。這章把 H3「房間裡擺什麼家具」的選項全擺出來,配一張決策表。

---

## Part A · 同一個 `Order`,兩種擺法

### 貧血模型(Anemic):對象是「數據袋」,邏輯全在 Service
```java
// 領域對象:只有 getter/setter,沒有行為。它什麼都不「會」,只是裝數據
class Order {
    Long id; OrderStatus status; List<OrderLine> lines; Money total;
    // ... 一堆 get/set
}

// 業務邏輯全堆在 service
class OrderService {
    void cancel(Long orderId) {
        Order o = repo.findById(orderId);
        if (o.getStatus() == SHIPPED) throw new IllegalState("已發貨不能取消");
        if (o.getStatus() == CANCELLED) throw new IllegalState("已取消");
        o.setStatus(CANCELLED);
        repo.save(o);
    }
}
```

### 充血模型(Rich):對象自己「會」做事,規則住在對象裡
```java
class Order {
    private OrderStatus status;
    // ...
    void cancel() {                                  // 行為在對象身上
        if (status == SHIPPED)   throw new IllegalState("已發貨不能取消");
        if (status == CANCELLED) throw new IllegalState("已取消");
        this.status = CANCELLED;                     // 規則和狀態在一起,外人改不了
    }
}

class OrderService {                                 // service 退化成「編排」
    void cancel(OrderId id) {
        Order o = repo.findById(id);
        o.cancel();          // 把「怎麼取消」交給對象自己
        repo.save(o);
    }
}
```

> 🔬 **核心差別不是「方法寫哪」,是「業務不變量(invariant)住哪」**:
> - **貧血**:不變量散落在各個 service。`Order` 的 setter 公開,任何人都能 `o.setStatus(CANCELLED)` **繞過**所有檢查——規則守不住,哪天另一個 service 漏了一個判斷,就是 bug。
> - **充血**:狀態 `private`,改它的唯一入口是 `cancel()`,**不可能造出一個非法的 Order**。這就是 **Tell-Don't-Ask**(別問對象狀態再自己判斷,直接命令對象做事)。
>
> 充血的價值,在規則**複雜且必須守住**時才顯現;規則就一兩條、或根本沒規則(純存取),充血只是徒增儀式。

---

## Part B · Transaction Script:你天天在寫,它有名字

「貧血 + service 把流程從頭跑到尾」這個寫法,Fowler 給了名字:**Transaction Script(事務腳本)**——**一個業務操作 = 一個過程式方法,從上到下:取數據 → 判斷 → 改 → 存**。上面那個貧血版 `cancel()` 就是。

**別污名化它** 🔬:Transaction Script 是 Fowler 在《企業應用架構模式》裡**正式推薦**的模式之一,適用於**邏輯簡單**的場景。企業裡 80% 的後台、報表、CRUD,事務腳本是**又快又好懂的正解**,上 DDD 反而是負擔。

| Transaction Script 何時閃光 | 何時開始腐爛 |
|---|---|
| 邏輯簡單、流程直白 | 同樣的規則在多個腳本裡**複製貼上** |
| 改動少、規則穩定 | 單個腳本長到 300 行、巢狀 if 五層 |
| CRUD、後台、報表 | 規則開始**互相糾纏**(這時該換充血了) |

> 一句話:**Transaction Script 不是「low」,是「合適」**。它腐爛的信號(邏輯重複、腳本爆長)出現時,才是該升級到充血/戰術 DDD 的時機。

---

## Part C · Active Record vs Repository(別混)

「對象怎麼和資料庫打交道」也有兩種家具:

| | **Active Record** | **Data Mapper / Repository** |
|---|---|---|
| 對象 = ? | **對象就是一行表記錄**,自己會存自己 | 領域對象**純業務**,不知道資料庫 |
| 長相 | `user.save()`、`User.find(1)` | `userRepo.save(user)`(`01`/`04` 那個) |
| 代表 | Rails AR、Django ORM、Eloquent、MyBatis-Plus AR 模式 | JPA/Hibernate、`01` 的 Repository |
| 取捨 🔬 | **快、省、直觀**,但領域和表結構**焊死** | 領域**純淨可測**,但要映射(對象↔表),**儀式重** |
| 配誰 | 配貧血 / Transaction Script | 配充血 / 戰術 DDD |

> 🔬 內幕:Active Record 把「業務對象」和「持久化」合一——爽在快,痛在**表結構一改,業務對象跟著改**,且很難脫離 DB 測試。Repository(Data Mapper)把兩者分開——這正是 `04` 依賴反轉的應用:領域定義 `Repository` 接口,持久化去實現。**選哪個,還是看複雜度**:簡單 CRUD 用 Active Record 爽,複雜核心域用 Repository 保純淨。

---

## Part D · 「貧血是反模式嗎?」——最容易答錯的一題

Fowler 2003 確實寫過一篇把 Anemic Domain Model 叫「反模式」。但**斷章取義就會答錯**:

- 他批的是這種情況:你**有複雜的業務邏輯**,卻把它全抽到 service、讓領域對象當數據袋——**付了領域模型的成本(對象↔表映射),卻沒拿到它的好處(行為內聚、守住不變量)**。這才叫反模式。
- 但對**本質簡單的 CRUD**,貧血 + Transaction Script **不是反模式,是恰當**。Fowler 自己也推薦簡單場景用 Transaction Script。

> 🔬 **真正的判據(一句話)**:**這份數據有沒有「值得守護的不變量/行為」?**
> - **有**(訂單能不能取消、賬戶餘額不能為負、保單核保規則)→ 該充血,把規則關進對象。
> - **沒有**(就是存進去、查出來、改個字段)→ **貧血就是對的**,別硬塞行為。
>
> 所以「貧血 vs 充血」**不是道德問題,是匹配問題**:複雜邏輯用貧血(規則散落)= bug 農場;簡單 CRUD 用充血(空洞儀式)= 過度設計。**兩個方向錯配都是病。**

---

## Part E · 決策表:H3 該擺什麼家具

| 情況 | 建模 | 持久化 | 為什麼 |
|---|---|---|---|
| 核心域、規則複雜且必須守、常變 | **充血 / 戰術 DDD**(`02`) | Repository | 不變量關進聚合,規則守得住、改得動 |
| 支撐域、流程直白、規則簡單穩定 | **貧血 + Transaction Script** | Repository 或 Active Record | 又快又好懂,別上儀式 |
| 純 CRUD、後台、原型 | 貧血 | **Active Record** | 最省,直接對表 |

**生態視角(別把 Java 當唯一正解)** 🔬:
- **Go**:文化反 OOP 儀式,**幾乎一律貧血 + 函數/service**——在 Go 裡這是**慣用法、是優點**,不是落後。
- **Java / C#**:OOP 重,充血最自然,戰術 DDD 生態成熟。
- **Python**:兩者都行;Django 偏 Active Record,純業務也可手寫充血。
- 結論:**語言文化會把默認推向某一邊,但判據不變——看數據有沒有值得守的不變量。**

---

## 面試滿分答法

> **Q:「貧血模型是不是反模式?」**
> 滿分:「**看情況,不是非黑即白。** Fowler 批的是『有複雜邏輯卻硬抽到 service、領域對象當數據袋』——那是付了映射成本沒拿到內聚好處。但對本質 CRUD,貧血 + Transaction Script 是恰當的、甚至更好。**判據是:這份數據有沒有值得守護的不變量?有就充血,沒有貧血就對。** 把充血儀式套到 CRUD 上,才是另一種過度設計。」

> **Q:「你怎麼決定業務邏輯放哪——對象裡還是 service 裡?」**
> 「先問複雜度。**規則複雜且要守住不變量**(訂單能否取消、餘額不能為負),我放進對象用充血,讓非法狀態根本造不出來(Tell-Don't-Ask);**流程簡單的 CRUD**,我用事務腳本放 service,別硬塞行為。Go 項目我默認偏貧血,Java 核心域偏充血。」

---

## 本章小結

- **貧血 vs 充血,差在「不變量住哪」**:貧血散落在 service(setter 公開、可繞過);充血關進對象(`private` 狀態 + 行為,造不出非法對象,Tell-Don't-Ask)。
- **Transaction Script** 是你天天寫的那個,**正當模式**,簡單邏輯的正解;腐爛信號(邏輯重複、腳本爆長)才是升級充血的時機。
- **Active Record(對象=表行,自己存自己)vs Repository(領域純淨、`04` 依賴反轉)**:前者快但焊死、配貧血,後者純淨但儀式重、配充血。
- **「貧血是反模式」要分情況**:複雜邏輯硬貧血才是反模式;簡單 CRUD 貧血是恰當。**判據:數據有沒有值得守的不變量。**
- **錯配都是病**:CRUD 上充血 = 過度設計;複雜域用散落貧血 = bug 農場。Go 默認貧血(慣用)、Java 核心域充血。
- ✅ **打底首批(00/01/04/03)完成。** 下一章 `02`(續寫批)**DDD 戰術設計**:當你決定要充血,**怎麼正確地做**——Entity / Value Object / **Aggregate 一致性邊界** / Repository / Domain Service。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 貧血和充血模型,**最核心**的差別是什麼?(提示:不變量住哪,不是方法寫哪)
2. 為什麼說貧血模型的公開 setter 是個隱患?充血怎麼解?Tell-Don't-Ask 是什麼?
3. Transaction Script 是什麼?它是「low」嗎?它什麼時候閃光、什麼時候開始腐爛?
4. Active Record 和 Repository 差在哪?各配貧血還是充血?各自的取捨?
5. 「貧血模型是反模式」這句話對嗎?Fowler 到底在批什麼?
6. 決定充血還是貧血的**一句話判據**是什麼?
7. 為什麼說「CRUD 上充血」和「複雜域用貧血」都是病?
8. Go、Java、Python 在這題上的默認傾向分別是什麼?判據會因語言而變嗎?
9. **面試題 A**:「貧血模型是不是反模式?」給出分情況的滿分答法。
10. **面試題 B**:「業務邏輯該放對象還是 service?」用複雜度給出判斷框架。
