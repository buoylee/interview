# 04 · 错误设计实战：API 边界该暴露什么错误

> 这是本 track 的**架构师重心**，也是「Go 错误处理最佳实践」面试题的正面回答。前面三章讲机制（error 是值 / 三种风格 / `%w`·`Is`·`As`）；本章讲**取舍**：你写一个包，它对外**暴露什么错误**、错误怎么**分层**、怎么**不泄漏内部**、怎么**不重复包装**、错误和日志怎么**分工**。
>
> 一句话立场：**错误是你的 API 契约。** 调用方会依赖你返回的错误去做判断，所以「返回什么错误」是设计问题，不是随手 `return err`。

---

## 1. 核心问题

面试官最爱问的那道题，其实是四个连环问：

1. 你的函数失败了，该向调用方**暴露什么**？原始的底层错误，还是包装过的？
2. DB 层的 `sql: no rows`、HTTP handler、领域逻辑——错误怎么**分层**才不互相泄漏？
3. 同一个错误，要不要**既 log 又 return**？谁负责打日志？
4. 一层层 `fmt.Errorf("xxx failed: %w", err)` 包上去，会不会**重复包装**成一坨噪音？

答不好这四问，就是「会用 `errors.Is` 但没设计过错误」。本章逐个拆。

---

## 2. 直觉理解

### 错误是 API 契约的一部分

调用方拿到你的错误后会这样用：

```go
if errors.Is(err, repo.ErrNotFound) { return http.StatusNotFound }
```

这一刻，`repo.ErrNotFound` 就**变成了你包的公共契约**——和函数签名一样，一旦发布就不能随便改，改了就破坏调用方。所以：

> 你**故意暴露**的错误（哨兵、错误类型、行为接口）= 公共 API；其余的底层错误 = 实现细节，应当被「翻译」掉，不让它穿透边界。

类比 Java：你不会让 DAO 层的 `SQLException` 一路 `throws` 冒泡到 Controller——你会在边界 catch 它、翻译成领域异常（`OrderNotFoundException`）。Go 没有自动冒泡，但**同样的边界翻译纪律照样要做**，只是改成手动 `return 领域错误`。

### 两条贯穿全章的红线

- **信任边界（trust boundary）**：跨进程/对外的边界（HTTP 响应、RPC 返回）**绝不**把内部错误原文吐出去——既泄漏实现（表名、SQL、文件路径）又是安全问题。
- **抽象边界（abstraction boundary）**：跨包/跨层的边界，底层错误要翻译成本层的领域错误，否则上层就被你的实现细节**耦合**了（今天换个 ORM，错误类型全变，调用方全崩）。

---

## 3. 原理深入

### 3.1 调用方有三种「识别错误」的方式——决定你该暴露什么

| 暴露方式 | 调用方怎么识别 | 耦合度 | 何时用 |
|---|---|---|---|
| **sentinel 哨兵**（`var ErrNotFound = errors.New(...)`） | `errors.Is(err, ErrNotFound)` | 中（调用方依赖这个变量） | 少数稳定的「类别」：not found / closed / EOF |
| **typed 错误类型**（自定义 struct） | `errors.As(err, &myErr)` 取出字段 | 高（调用方依赖具体类型 + 字段） | 错误要**携带数据**：哪个字段非法、第几行、重试间隔 |
| **behavior 行为接口**（`interface{ Temporary() bool }`） | 断言行为而非类型 | **低** | 调用方只关心「能不能重试/是不是临时」，不关心是谁 |

设计准则（Dave Cheney 的经典建议）：**断言行为，而非类型（assert errors for behaviour, not type）**。能用行为接口表达的，就别逼调用方依赖你的具体类型或哨兵——耦合最低、最好演进。

```go
// 调用方不关心是 net.Error 还是你的自定义类型，只关心"是不是临时的、能不能重试"
type temporary interface{ Temporary() bool }
func isTemporary(err error) bool {
    var t temporary
    return errors.As(err, &t) && t.Temporary()
}
```

> 三选一不是互斥：哨兵给「类别」，类型给「带数据」，行为接口给「只问能力」。**最佳实践是尽量减少公共哨兵/类型的数量**——每多暴露一个，就多一份要长期维护的契约。

### 3.2 `%w` vs `%v`：一个被忽略的「要不要暴露」开关

包装错误时这两个选择，本质是**契约决策**：

```go
return fmt.Errorf("query user: %w", err)   // %w：把底层 err 接进链，调用方能 Is/As 到它
return fmt.Errorf("query user: %v", err)   // %v：只取文字，故意"切断链"，底层错误不再可被 Is/As
```

- 用 `%w`：你**承诺**底层错误是你契约的一部分，调用方可以 `errors.Is(err, sql.ErrNoRows)`。——但这就把 `database/sql` 的错误**泄漏进了你的契约**，换实现会破坏调用方。
- 用 `%v`（或干脆返回新错误）：你**故意不透明化**，把底层错误降级为「日志可见、但不进契约」。这正是**跨抽象边界翻译**的手法。

口诀：**包内/同层传递用 `%w`（保留链方便上层诊断）；跨公共边界翻译时用 `%v` 或返回领域哨兵（切断对内部的耦合）。**

### 3.3 错误分层模型

```
HTTP/gRPC 边界   ── 翻译成 状态码 + 安全文案（对外，绝不漏内部）
      ↑ 领域错误（ErrOrderNotFound / ErrInsufficientBalance）
service 层       ── 把基础设施错误翻译成领域错误
      ↑ 基础设施错误（sql.ErrNoRows / redis.Nil / net 超时）
repo/client 层   ── 产生底层错误，用 %w 加上下文上抛
```

每跨一层，做一次「**加上下文**（同层）或**翻译**（跨抽象/信任边界）」的决策。底层错误**不应该**裸奔到最顶层。

### 3.4 「处理一次」原则（handle once）

一个错误，要么**处理它**（log / 转译 / 重试 / 兜底），要么**返回它**（`return err`）——**不要两者都做**。

```go
// ❌ 反模式：既 log 又 return —— 同一个错误被打印 N 次（每层一次），日志爆炸还难定位
if err != nil {
    log.Printf("query failed: %v", err)   // 这层打了
    return err                            // 上层接住又打一次……一路打到顶
}

// ✅ 底层只加上下文上抛，不打日志
if err != nil {
    return fmt.Errorf("query user %d: %w", id, err)
}
// ✅ 只在最顶层（请求边界 / main）打一次，带完整错误链
if err := handle(req); err != nil {
    log.Printf("request failed: %v", err)   // 唯一一次，%v 会展开整条 %w 链
}
```

谁负责打日志？——**最终处理错误的那一层**（通常是请求入口的中间件、或 main）。中间各层只管「加上下文 + 上抛」。

---

## 4. 日常开发应用

### 模式一：包级哨兵 + 边界翻译

```go
// repo 包：暴露稳定的领域哨兵
package repo
var ErrNotFound = errors.New("repo: not found")

func (r *UserRepo) Get(ctx context.Context, id int) (*User, error) {
    err := r.db.QueryRowContext(ctx, "...", id).Scan(&u.Name)
    if errors.Is(err, sql.ErrNoRows) {
        return nil, ErrNotFound              // 把 sql 错误翻译成领域哨兵（切断对 database/sql 的耦合）
    }
    if err != nil {
        return nil, fmt.Errorf("get user %d: %w", id, err)   // 其它错误加上下文上抛
    }
    return &u, nil
}
```

```go
// http 边界：把领域哨兵翻译成状态码 + 安全文案（不漏内部）
func handler(w http.ResponseWriter, r *http.Request) {
    u, err := repo.Get(ctx, id)
    switch {
    case errors.Is(err, repo.ErrNotFound):
        http.Error(w, "user not found", http.StatusNotFound)   // 对外文案，无内部细节
    case err != nil:
        log.Printf("get user: %v", err)                        // 内部完整链进日志
        http.Error(w, "internal error", http.StatusInternalServerError)  // 对外只给一句
    default:
        json.NewEncoder(w).Encode(u)
    }
}
```

这段就是面试题的**标准答案骨架**：repo 层翻译 sql→领域哨兵、http 层翻译领域→状态码、内部错误进日志、对外只给安全文案。

### 模式二:携带数据用 typed 错误 + `As`

```go
type ValidationError struct {
    Field string
    Msg   string
}
func (e *ValidationError) Error() string { return e.Field + ": " + e.Msg }

// 调用方取出结构化字段（不是 parse 字符串！）
var ve *ValidationError
if errors.As(err, &ve) {
    return fmt.Sprintf("字段 %s 不合法", ve.Field)
}
```

### 包装时加「一段」上下文，不重复

```go
// ✅ 每层加一段不同的、递进的上下文
//   "handle order 42: charge payment: call stripe: connection refused"
// ❌ 重复噪音："failed to ...: failed to ...: error: error: ..."
return fmt.Errorf("charge payment: %w", err)   // 上下文短句、动宾、不带 "failed to/error"
```

惯例：上下文写成**小写、动宾短语、不带标点结尾、不带 "failed/error"**——因为 `%w` 会用 `: ` 拼接，最终读起来是一条干净的「操作链」。

---

## 5. 生产&调优实战

- **对外响应做错误翻译 + 脱敏**：跨信任边界（HTTP/RPC/对外日志）绝不回传内部错误原文。给客户端的是「状态码 + 稳定 error code + 安全文案」，内部细节只进服务端日志。否则泄漏表结构/路径/依赖，既是安全问题也帮攻击者摸底。
- **错误里别塞敏感数据**：错误信息会进日志、可能被采集到可观测平台。别把 token、密码、PII 拼进 `Error()`。
- **错误码 vs 错误文案**：对外 API 用稳定的 **error code**（字符串/枚举）让客户端判断，文案仅供人读、可改。code 是契约，文案不是。
- **可观测性分工**：error 负责「带因果链回到边界」，到边界后：① 打**结构化日志**（带 trace_id，`%+v`/`%v` 展开链）；② 计 **metric**（error 计数按 code 分类）；③ 记 **span 状态**（OTel `span.RecordError` + `SetStatus`）。链接 `observability/`。日志只打一次（handle once）。
- **要不要堆栈轨迹？** 标准库 error **不带** stack trace（这是它和 Java 异常的一大差异，也是它便宜的原因）。需要堆栈时：用 `log/slog` 在边界记录、或引入带 stack 的错误库（如 `pkg/errors` 的 `%+v`，社区现多用 `Is/As` + 结构化日志替代）。是否引入是团队取舍——多数服务靠「`%w` 链 + 边界日志 + trace」已经够定位。
- **错误是兼容性契约**：删/改一个已发布的哨兵或错误类型 = 破坏性变更。新增错误信息文字一般安全，但**改变 `Is/As` 的匹配结果**要当 API 变更对待。

---

## 6. 面试高频考点

- **「Go 错误处理最佳实践」一句话框架？** 错误是 API 契约：① 同层传递用 `%w` 加上下文；② 跨抽象/信任边界**翻译**（底层错误 → 领域哨兵/状态码，用 `%v` 或新错误切断耦合）；③ 错误**只处理一次**（要么 return 要么 log，别both，日志在边界打一次）；④ 对外**脱敏**不漏内部；⑤ 调用方识别错误优先**断言行为**，其次哨兵/类型。
- **API 该暴露什么错误？** 故意暴露的（哨兵/类型/行为接口）才是契约，数量尽量少；底层实现错误要翻译掉、不让穿透边界。
- **`%w` 和 `%v` 包装时怎么选？** `%w` 把底层错误接进链、调用方能 `Is/As`（= 承诺它进契约）；`%v` 切断链、故意不透明（= 跨边界翻译、不泄漏内部耦合）。
- **同一个错误要不要又 log 又 return？** 不要。handle once——中间层只加上下文上抛，日志只在最终处理的那层（请求入口/main）打一次，避免一条错误被打 N 遍。
- **怎么避免重复包装？** 每层只加**一段递进的、动宾短语**上下文，不写 "failed to"，靠 `%w` 的 `: ` 拼成一条干净操作链。
- **哨兵 vs 错误类型 vs 行为接口？** 哨兵给稳定类别（`Is`）；类型给携带数据（`As` 取字段）；行为接口给「只问能力」（断言 `Temporary()` 等），耦合最低、最推荐优先。
- **DAO 的 sql 错误要不要冒泡到 controller？** 不要——在 repo/service 边界翻译成领域错误，否则上层被实现细节耦合、换实现就崩；和 Java「别让 SQLException 冒泡到 Controller」同理。

---

## 7. 一句话总结

> **错误是 API 契约，设计它而不是随手 return。** 五条最佳实践：① 同层用 `%w` 加**一段递进上下文**上抛；② 跨抽象/信任边界做**翻译**（底层错误→领域哨兵/状态码，用 `%v` 或新错误切断耦合、对外脱敏不漏内部）；③ 错误**只处理一次**（要么 return 要么 log，日志在请求边界打一次，绝不层层 log+return）；④ 调用方识别错误**优先断言行为**（`Temporary()`），其次哨兵（`Is`）/类型（`As` 带数据），**公共哨兵/类型数量越少越好**；⑤ 对外用稳定 **error code**、内部细节只进结构化日志 + trace。心法和 Java「DAO 异常别冒泡到 Controller、边界翻译」一致，只是 Go 把它从 try-catch 改成了手动 `return 领域错误`。

← 上一章 [`03 panic·recover·defer`](../03-panic-recover-defer/README.md) ｜ 下一章 → [`05 并发中的错误`](../05-concurrent-errors/README.md)：errgroup 首错取消、`errors.Join` 聚合、goroutine panic 为什么会整进程 crash。｜ 回 [`error-handling` 索引](../README.md)
