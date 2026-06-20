# 02 · encoding/json:tag、流式、自定义 Marshaler

> JSON 是服务间通信的通用语,`encoding/json` 是必备技能。面试常考:**struct tag(含 omitempty)、流式 Encoder/Decoder、自定义 Marshaler、以及「数字解进 interface{} 变 float64」的经典坑**。
>
> 桥接锚点:Java Jackson/Gson 用注解(`@JsonProperty`/`@JsonIgnore`)+ ObjectMapper;Go 用 struct tag + `json.Marshal/Unmarshal`,且**只序列化导出字段**(大写)。

---

## 1. 核心问题

```go
type User struct {
    Name  string `json:"name"`
    Email string `json:"email,omitempty"`
    pwd   string                         // 小写,会被序列化吗?
}
b, _ := json.Marshal(User{Name: "alice"})  // 输出什么?email 在吗?pwd 呢?
```

- struct tag 怎么控制字段名?`omitempty` 是什么?为什么 `pwd` 不出现?
- 处理大 JSON 流 / HTTP body,该用 `Marshal` 还是 `Encoder`?
- 把 JSON 解进 `interface{}`,数字为什么变成了 `float64`?

---

## 2. 直觉理解

### tag 控制映射,只有导出字段被处理

```go
type User struct {
    Name  string `json:"name"`            // → "name"
    Email string `json:"email,omitempty"` // 空值时省略该字段
    Age   int    `json:"-"`               // 永不序列化
    pwd   string                          // 小写=未导出 → json 包看不见,永远被忽略
}
```

- **只有导出字段(大写开头)** 会被 Marshal/Unmarshal——`pwd` 永远不出现(json 包用反射,访问不了未导出字段)。
- `json:"name"` 改字段名;`omitempty` 让**零值字段省略**;`json:"-"` 完全忽略。

### Marshal vs Encoder:一次性 vs 流式

```go
b, _ := json.Marshal(v)                    // 一次性:对象 → []byte(整个进内存)
json.NewEncoder(w).Encode(v)               // 流式:直接写到 io.Writer(如 http response)
json.NewDecoder(r).Decode(&v)              // 流式:从 io.Reader(如 request body)读
```

处理 HTTP body / 大数据用 **Encoder/Decoder**(直接对接 io.Reader/Writer,不必先 ReadAll 进内存,承接 [`00 io`](../00-io/README.md));小对象用 Marshal/Unmarshal。

---

## 3. 原理深入

### 3.1 数字解进 interface{} 变 float64(经典坑)

```go
var data map[string]interface{}
json.Unmarshal([]byte(`{"id": 123}`), &data)
data["id"]                                 // 是 float64(123),不是 int!
id := data["id"].(int)                     // ❌ panic:interface conversion
id := int(data["id"].(float64))            // ✅
```

JSON 没有「整数/浮点」之分,Go 把数字解进 `interface{}` 时**一律用 `float64`**。所以解进 map/`any` 后取数字要断言 `float64`。要保留精度(大整数)用 `json.Decoder` + `UseNumber()`(得到 `json.Number`,可转 int64/string)。**解进具体 struct 字段(`int`/`int64`)则没这问题**——按字段类型解。

### 3.2 自定义 Marshaler/Unmarshaler

类型可实现接口改写序列化:

```go
type Marshaler interface { MarshalJSON() ([]byte, error) }
type Unmarshaler interface { UnmarshalJSON([]byte) error }

// 例:把 time 序列化成自定义格式、把枚举序列化成字符串
func (c Color) MarshalJSON() ([]byte, error) {
    return json.Marshal(c.String())        // 枚举 → "red" 而非数字
}
```

用于:自定义时间格式、枚举↔字符串、加密字段、兼容老格式。

### 3.3 其它常用

- **`json.RawMessage`**:延迟解析——先把一段原样存着,之后按需再 Decode(处理多态/未知结构的 payload)。
  ```go
  type Envelope struct { Type string; Data json.RawMessage }
  ```
- **`DisallowUnknownFields`**:`dec.DisallowUnknownFields()` 让 JSON 里有未知字段时报错(严格校验,默认是忽略多余字段)。
- **嵌入字段平铺**:嵌入的 struct 字段默认平铺到外层 JSON(承接 [`type-system/04`](../../type-system/04-embedding/README.md))。
- **指针 vs omitempty 区分「零值」和「缺失」**:`*int` 能区分「字段是 0」和「字段没传」(nil),普通 `int` 不能。

### 3.4 性能

标准库 json 用反射,够用但非最快。极致性能场景社区有 `json-iterator`、`easyjson`(代码生成,见 [`generics/02`](../../generics/02-when-to-use/README.md))、`sonic`(字节跳动,SIMD);但默认 stdlib 应是首选,有瓶颈再换。

---

## 4. 日常开发应用

- **字段加 tag**:`json:"snake_case"`(Go 字段大写驼峰、JSON 常 snake);可选字段 `omitempty`;敏感字段 `json:"-"`。
- **HTTP 用 Encoder/Decoder** 直接对接 body,别 ReadAll + Marshal。
- **解进 map/any 时数字记得断言 float64**;要 int64 精度用 `UseNumber()`。
- **自定义格式/枚举字符串用 MarshalJSON**。
- **多态/未知 payload 用 `json.RawMessage`** 延迟解析。
- **严格校验用 `DisallowUnknownFields`**;区分缺失/零值用指针字段。

---

## 5. 生产&调优实战

- **未导出字段不序列化**是特性也是坑:想导出必须大写 + tag;敏感数据(密码)放未导出或 `json:"-"` 防泄漏(呼应 [`error-handling/04`](../../error-handling/04-error-design/README.md) 不泄漏内部)。
- **float64 精度坑**:大整数(如雪花 ID)解进 `interface{}` 会丢精度(float64 只能精确表示 2^53 内整数);用 `json.Number` 或解进 `int64`/string 字段。
- **Decoder 流式省内存**:大响应用 `json.NewDecoder(resp.Body).Decode`,避免 ReadAll 整个进内存(配 [`01 net/http`](../01-net-http/README.md))。
- **DisallowUnknownFields 用于 API 入参校验**:拒绝拼写错误/多余字段,早发现客户端 bug。
- **反射性能**:超高 QPS 的序列化热点可换 easyjson/sonic;一般场景 stdlib 够,先 profile。

---

## 6. 面试高频考点

- **struct tag / 什么字段会被序列化?** 只有**导出字段**(大写);`json:"name"` 改名、`omitempty` 省零值、`json:"-"` 忽略。未导出字段 json 包访问不到、永远忽略。
- **数字解进 interface{} 为什么是 float64?** JSON 不分整数/浮点,Go 解进 `any` 一律用 float64;取时断言 float64;要精度用 `UseNumber()`/`json.Number` 或解进具体类型。
- **Marshal vs Encoder?** Marshal 一次性进内存;Encoder/Decoder 流式对接 io.Reader/Writer,处理 HTTP body/大数据用它。
- **自定义序列化?** 实现 `MarshalJSON`/`UnmarshalJSON`(枚举↔字符串、自定义时间格式)。
- **json.RawMessage 干嘛?** 延迟解析,处理多态/未知结构 payload。
- **怎么区分「字段为 0」和「字段缺失」?** 用指针字段(`*int`,nil=缺失);普通 int 区分不了。
- **怎么严格校验入参?** `Decoder.DisallowUnknownFields()`。

---

## 7. 一句话总结

> **encoding/json 用 struct tag 控制映射,且只序列化导出字段**(`json:"name,omitempty"`、`json:"-"`;未导出字段永远忽略——可用于藏敏感数据)。**Marshal/Unmarshal 一次性进内存,Encoder/Decoder 流式对接 io.Reader/Writer**(HTTP body/大数据用后者,省内存)。经典坑:**数字解进 `interface{}` 一律是 `float64`**(JSON 不分整浮),取时断言 float64、要精度用 `UseNumber()`/`json.Number` 或解进具体类型(大整数 ID 尤其小心丢精度)。进阶:`MarshalJSON`/`UnmarshalJSON` 自定义(枚举↔字符串)、`json.RawMessage` 延迟解析多态 payload、`DisallowUnknownFields` 严格校验、指针字段区分缺失 vs 零值。

← 上一章 [`01 net/http`](../01-net-http/README.md) ｜ 下一章 → [`03 database/sql`](../03-database-sql/README.md):sql.DB 为什么是「连接池」不是「连接」、连接池参数、事务、context、必须 rows.Close 的坑。｜ 回 [`stdlib` 索引](../README.md)
