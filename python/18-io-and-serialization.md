# 17 · 文件 I/O 与序列化

> **为什么这章重要**:读写文件、和外部系统交换数据(JSON/CSV/pickle)是日常后端的水电活,但每个点都有坑——文本 vs 二进制、编码、流式 vs 全量加载,尤其 **pickle 反序列化能执行任意代码**(高频安全面试题)。这章把"数据进出 Python"讲清楚。

## 一、文件读写:永远用 `with` + 指定编码

```python
# 写
with open("t.txt", "w", encoding="utf-8") as f:
    f.write("héllo\n世界\n")

# 读
with open("t.txt", "r", encoding="utf-8") as f:
    for line in f:                 # 直接迭代文件 = 逐行流式读,不全量载入
        print(line.rstrip())
```

要点:

- **`with`**:保证文件被关闭(异常时也关),别手动 `open()` + `close()`(第 07 章)。
- **显式 `encoding="utf-8"`**:不指定会用平台默认编码(Windows 上可能是 GBK/cp1252),是跨平台乱码的头号来源。**永远显式写编码。**
- **文件对象本身可迭代**:`for line in f` 是**逐行流式**读取,内存恒定——读大文件别用 `f.read()`(一次性全进内存)或 `f.readlines()`。

### 文本模式 vs 二进制模式

```python
with open("t.txt", "rb") as f:     # 'b' = 二进制,返回 bytes
    raw = f.read()
print(len(raw))                     # 14 —— 字节数(é/中文每个多字节),不是字符数
```

- **文本模式**(`"r"`/`"w"`):读写 `str`,自动按 `encoding` 编解码、自动处理换行符。
- **二进制模式**(`"rb"`/`"wb"`):读写 `bytes`,不做任何编码转换。图片、压缩包、网络协议、要精确控制字节时用它。

记住第 02 章的区分:文本是 `str`(字符),二进制是 `bytes`(字节),一个中文字符在 UTF-8 里占 3 字节——所以 `len(文本)` 和 `len(字节)` 不同。

## 二、JSON

```python
import json
json.dumps({"x": "中", "n": 1})                    # '{"x": "\\u4e2d", "n": 1}' 默认转义非 ASCII
json.dumps({"x": "中"}, ensure_ascii=False)        # '{"x": "中"}' ← 中文场景要加这个
json.loads('{"x": 1}')                              # {'x': 1}

with open("c.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)   # dump 直接写文件
```

两个常见点:

- **中文**:默认 `ensure_ascii=True` 会把中文转成 `\uXXXX`,加 `ensure_ascii=False` 保留原文。
- **非内置类型**(如 `datetime`)默认不可序列化,用 `default=` 钩子:

```python
import datetime
def enc(o):
    if isinstance(o, datetime.date):
        return o.isoformat()
    raise TypeError(f"不可序列化: {type(o)}")
json.dumps({"d": datetime.date(2026, 6, 14)}, default=enc)   # '{"d": "2026-06-14"}'
```

> 类型映射:JSON 的 object↔dict、array↔list、null↔None、true/false↔True/False。注意 JSON 的 key 只能是字符串——`json.dumps({1: "a"})` 会把 key 转成 `"1"`。

> **小知识:`\\u4e2d` 到底是什么?为什么 LLM 返回的中文全是它?**
>
> 先分清三个常被混为一谈的概念:
> - **ASCII**:最老的字符集,只有 128 个字符——英文字母、数字、标点,**没有中文/emoji**。
> - **Unicode**:超大字符集,给全世界字符都编了号(`中` = `U+4E2D`、`😀` = `U+1F600`)。**ASCII 是 Unicode 最前面那 128 个的子集**(`A` 在两边都是 65,故意兼容)。
> - **转义 `\\uXXXX`**:一种**写法**,用「反斜杠 + 该字符的 Unicode 编号」把一个非 ASCII 字符表示出来——而 `\\` `u` `4` `e` `2` `d` 这 6 个字符本身全是 ASCII。
>
> 所以 `ensure_ascii=True`(默认)的完整逻辑是:**"输出只准是 ASCII → `中` 超出 ASCII → 用 `\\u4e2d` 转义"**。`\\u4e2d` 和 `中` 是**同一个字的两种拼法**,`json.loads` 时都还原成 `中`,数据没丢。
>
> **常见坑:某接口 / LLM 返回的中文全是 `\\u4e2d`,怎么修?** 关键——**没有「ASCII 解码」这种操作**,把它变回 `中` 的是 JSON 解析器。先看你在哪儿看到的:
>
> | 看到 `\\u4e2d` 的地方 | 真相 | 修法 |
> |---|---|---|
> | 一段未解析的 **JSON 文本** | 还没解析 | `json.loads(s)` 自动还原 |
> | 你自己又 `json.dumps()` 去存/返回 | 默认又转义回去 | 加 `ensure_ascii=False` / 用 orjson / 靠框架默认 |
> | `print(已解析的 dict)` | 只是 `repr` 显示形式 | 直接 `print(d["key"])` 即中文,非 bug |
>
> LLM 的响应体本就是 JSON,SDK 通常已 `json.loads`,中文早在内存里好好的——满屏 `\\u4e2d` 多半是**你在输出端又 dump 回去了**。用 FastAPI 直接 `return data` 不会有此问题(`JSONResponse` 默认 `ensure_ascii=False`),所以别手动 `json.dumps` 再返回。

## 三、CSV

别手动 `split(",")`(字段里有逗号、引号、换行就崩),用标准库 `csv`:

```python
import csv
with open("d.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["name", "age"])
    w.writerow(["Ann", "30"])

with open("d.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):       # 用表头当 key
        print(row)                       # {'name': 'Ann', 'age': '30'}
```

要点:**打开 CSV 文件要加 `newline=""`**(让 csv 模块自己处理换行,否则 Windows 上会多出空行);`DictReader`/`DictWriter` 用表头映射成 dict,比按下标取列健壮。

## 四、pickle:Python 专用序列化(及其安全雷区)

`pickle` 能把**几乎任意 Python 对象**序列化成字节流再还原——dict、自定义对象、嵌套结构都行:

```python
import pickle
obj = {"a": [1, 2, 3], "b": (4, 5)}
data = pickle.dumps(obj)              # 对象 → bytes
print(pickle.loads(data) == obj)     # True,完整还原
```

它比 JSON 强在:保留 Python 类型(tuple 不会变成 list)、能存自定义对象。但有两个限制 + 一个致命安全问题:

- **不是什么都能 pickle**:lambda、本地函数、打开的文件/socket、线程锁等不能。
  ```python
  pickle.dumps(lambda x: x)          # PicklingError
  ```
- **跨语言不通用**:pickle 是 Python 私有格式,别用它和别的语言/系统交换数据(那是 JSON 的活)。

### ⚠️ pickle 反序列化 = 执行任意代码(高频安全题)

`pickle.loads` **不只是读数据,它会执行构造对象的代码**。对象可通过 `__reduce__` 指定"还原时调用什么"——攻击者可以让它调用任意函数:

```python
import pickle
class Evil:
    def __reduce__(self):
        return (print, ("反序列化时执行了任意代码!",))

pickle.loads(pickle.dumps(Evil()))   # 直接打印 —— loads 期间就执行了!
# 把 print 换成 os.system / subprocess,就是远程代码执行(RCE)
```

**铁律:绝不要 `pickle.loads` 来自不可信来源的数据**(用户上传、网络请求、外部缓存)。这等同于执行对方给的代码。可信场景(自己进程间、自己写的缓存)才用 pickle;对外交换一律用 JSON。需要安全的结构化序列化用 JSON;需要带类型校验的用 pydantic(第 14 章)。详见[第 19 章](19-security.md)。

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 文件读写 | `Files`/`BufferedReader`、Go `os`/`bufio` | `with open(..., encoding=)`,文件对象可迭代逐行 |
| 编码 | `Charset` 显式 | 必须显式 `encoding=`,否则用平台默认(坑) |
| JSON | Jackson/Gson、`encoding/json` | 标准库 `json`(`default=`/`ensure_ascii`) |
| 对象序列化 | Java `Serializable`(也有反序列化漏洞!)、Go `gob` | `pickle`(同样有反序列化 RCE 风险) |
| 反序列化安全 | Java 反序列化漏洞臭名昭著 | `pickle.loads` 不可信数据 = RCE,同源问题 |

有意思的对照:**Java 的原生序列化反序列化漏洞**和 **Python 的 pickle** 是同一类问题——反序列化不可信数据等于让对方执行代码。从 Java 来的你对这点应该有共鸣。

## 章末面试卡

**Q1. 读大文件怎么避免内存爆掉?**
直接迭代文件对象 `for line in f`(逐行流式,内存恒定),或按块 `f.read(size)`;不要用 `f.read()`/`f.readlines()` 一次性全载入。

**Q2. `open` 为什么要显式指定 `encoding`?**
不指定时用平台默认编码(Windows 可能是 GBK/cp1252,Linux/mac 多为 UTF-8),导致同一份代码在不同平台读出乱码或报 `UnicodeDecodeError`。显式 `encoding="utf-8"` 才可移植。文本模式读写 `str`,二进制模式(`"rb"`)读写 `bytes` 不做编码转换。

**Q3. `json.dumps` 中文变成 `\uXXXX` 怎么办?非内置类型(如 datetime)怎么序列化?**
加 `ensure_ascii=False` 保留中文;非内置类型传 `default=` 钩子函数把它转成可序列化形式(如 `date.isoformat()`),否则抛 `TypeError`。

**Q4. pickle 和 JSON 怎么选?**
JSON:跨语言、人可读、安全,用于对外数据交换;但只支持基本类型。pickle:Python 私有、能存几乎任意 Python 对象并保留类型,但不跨语言、且**反序列化不可信数据有 RCE 风险**。对外/不可信一律 JSON,仅在可信的 Python 内部场景用 pickle。

**Q5(安全·高频). `pickle.loads` 有什么安全风险?**
`pickle.loads` 在反序列化时会**执行**还原对象的代码(对象可通过 `__reduce__` 指定调用任意函数),因此对不可信数据 `loads` 等于执行攻击者代码,可导致远程代码执行(RCE)。绝不反序列化来自用户/网络/外部的 pickle 数据。这与 Java 原生反序列化漏洞同源。

**Q6. CSV 为什么不能直接 `line.split(",")`?**
因为字段内可能含逗号、引号、换行(被引号包裹),手动 split 会切错。用标准库 `csv`(`DictReader`/`writer`),并在打开文件时加 `newline=""` 让其正确处理换行。
