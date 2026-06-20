# encoding/json:tag·流式·float64 坑

## 一句话回答

`encoding/json` 用 struct tag 控制映射,**只序列化导出字段**(大写;`json:"name,omitempty"`、`json:"-"`;未导出字段永远忽略——可藏敏感数据)。`Marshal/Unmarshal` 一次性进内存,`Encoder/Decoder` 流式对接 `io.Reader/Writer`(HTTP body/大数据用后者省内存)。**经典坑:数字解进 `interface{}` 一律是 `float64`**(JSON 不分整数/浮点),取时要断言 `float64`、要精度用 `UseNumber()`/`json.Number` 或解进具体类型(大整数 ID 易丢精度,float64 只精确到 2^53)。

## 进阶

- `MarshalJSON`/`UnmarshalJSON`:自定义序列化(枚举↔字符串、时间格式)。
- `json.RawMessage`:延迟解析多态/未知 payload。
- `Decoder.DisallowUnknownFields()`:严格校验入参。
- **指针字段**区分「缺失」(nil)vs「零值」。
- 嵌入字段默认平铺到外层 JSON(type-system/04)。

## 证据链接

- 正文:[`02 encoding/json`](../02-encoding-json/README.md);string/[]byte [`data-structures/02`](../../../data-structures/02-string-bytes-rune/README.md)

## 易追问的延伸

- **为什么 pwd 不出现?** 未导出字段 json 包用反射访问不到,永远忽略。
- **大整数 ID 怎么不丢精度?** 解进 int64/string 字段,或 `json.Number`,别解进 interface{}。
- **性能不够?** easyjson/sonic(代码生成/SIMD);先 profile,stdlib 通常够。
- **和 Jackson?** Jackson 用注解 + ObjectMapper;Go 用 tag + Marshal/Unmarshal,只处理导出字段。
