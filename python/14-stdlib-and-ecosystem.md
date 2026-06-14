# 14 · 标准库与生态地图

> **为什么这章重要**:Python 号称"自带电池(batteries included)"——标准库极其丰富,很多你想自己写的工具其实已经有了。资深工程师的标志之一是**知道该伸手拿哪个**,而不是重造轮子。这章过一遍最常用的标准库模块,再给一张第三方生态地图(对标 Java 的 Guava/Lombok)。

## 一、`collections`:更好用的容器

```python
from collections import Counter, defaultdict, deque, namedtuple

Counter("aabbbc").most_common(2)    # [('b', 3), ('a', 2)] —— 计数神器

dd = defaultdict(list)              # 访问缺失键自动建默认值
dd["x"].append(1)                   # 不用先判断 key 在不在
# {'x': [1]}

dq = deque([1, 2, 3])              # 双端队列:两端增删都 O(1)
dq.appendleft(0); dq.popleft()     # list 的 pop(0) 是 O(n),deque 是 O(1)

Pt = namedtuple("Pt", "x y")       # 轻量不可变记录,可解包、可 .x 访问
Pt(1, 2).x                          # 1
```

- **`Counter`**:计数 + `most_common`,统计词频/去重计数一行搞定。
- **`defaultdict`**:省掉 `setdefault`/`if key in` 的样板。
- **`deque`**:**队列/栈**首选,头部操作 O(1)(`list` 头部是 O(n))。
- **`namedtuple`**:简单不可变记录(更结构化的选 `@dataclass`)。

## 二、`itertools` / `functools`:迭代与函数工具

```python
import itertools, functools
itertools.accumulate([1, 2, 3])         # 1 3 6 累积
itertools.chain(a, b)                   # 串接;islice/groupby/product 见第 07 章
functools.reduce(lambda a, b: a*b, [1,2,3,4])   # 24 折叠
functools.lru_cache                     # 记忆化缓存(第 04 章)
```

## 三、`pathlib`:面向对象的路径(别再用 os.path 拼字符串)

```python
from pathlib import Path
p = Path("/tmp/foo/bar.txt")
p.name      # 'bar.txt'
p.suffix    # '.txt'
p.stem      # 'bar'
p.parent    # Path('/tmp/foo')
Path("/tmp") / "a" / "b.txt"            # 用 / 拼路径:/tmp/a/b.txt
p.exists(); p.read_text(); p.write_text("hi")   # 读写一步到位
```

`pathlib` 用 `/` 运算符拼路径、方法直接读写,比 `os.path.join` + `open` 清爽得多,跨平台也更稳。新代码一律用 `pathlib`。

## 四、`datetime` / `zoneinfo`:时间与时区

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo          # 3.9+ 内置时区库(取代第三方 pytz)

dt = datetime(2026, 6, 13, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
dt.isoformat()                          # '2026-06-13T12:00:00+08:00'
(dt + timedelta(days=1)).date()         # 2026-06-14
```

要点:**优先用"带时区(aware)"的 datetime**,别用裸的"无时区(naive)"时间做跨时区计算。`zoneinfo` 是 3.9 起的标准库,不必再装 `pytz`。

## 五、`json` / `logging` / `re`

```python
import json
json.dumps({"a": 1, "中": 2}, ensure_ascii=False)   # '{"a": 1, "中": 2}'
json.loads('{"a": 1}')                                # {'a': 1}
```
> 处理中文记得 `ensure_ascii=False`,否则被转义成 `\uXXXX`。

```python
import logging
logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger(__name__)       # 用 __name__ 拿模块级 logger
log.info("hello")                        # INFO:...:hello(默认到 stderr)
```
> 日志心智:**用 `logging` 不用 `print`**;每个模块 `getLogger(__name__)`;只在**应用入口**配一次 `basicConfig`/handler(别在库/工具模块顶层配,见[第 10 章](10-modules-packages-imports.md))。

```python
import re
m = re.search(r"(\d+)-(\d+)", "order 12-34")
m.groups()                               # ('12', '34');热路径用 re.compile 预编译
```

## 六、其他常备标准库

| 模块 | 用途 |
|------|------|
| `os` / `sys` | 环境变量、路径、进程参数、`sys.argv` |
| `subprocess` | 调外部命令(`subprocess.run([...], capture_output=True)`) |
| `dataclasses` / `enum` | 数据类 / 枚举(第 05 章) |
| `typing` | 类型注解(第 09 章) |
| `contextlib` | `contextmanager`/`suppress`(第 07 章) |
| `concurrent.futures` / `asyncio` | 并发(第 13 章) |
| `decimal` / `fractions` | 精确数值(第 02 章) |

## 七、第三方生态地图(该伸手拿哪个)

标准库之外,这些是"几乎每个工程都会用"的库,对标 Java 的 Guava/Lombok/Apache Commons:

| 场景 | 首选 | 说明 |
|------|------|------|
| **数据模型 + 校验** | **pydantic** | 读类型注解做运行时校验/解析;配置、API、数据边界标配(对标 Lombok+ 校验) |
| | `attrs` / `dataclasses` | 纯数据类(无重校验时 `dataclasses` 够用) |
| **HTTP 客户端** | **httpx**(同步+异步)/ `requests`(同步经典) | 调 API |
| **Web 框架** | **FastAPI**(异步+自动文档)/ Flask(轻)/ Django(全家桶) | |
| **ORM / DB** | **SQLAlchemy**(最主流)/ SQLModel / Tortoise(异步) | |
| **CLI** | **typer**(基于类型注解)/ click | 命令行工具 |
| **终端输出** | **rich**(彩色/表格/进度)/ tqdm(进度条) | |
| **数据/科学** | **numpy**(数组基石)/ **pandas**(表格)/ polars(Rust,快) | |
| **机器学习** | scikit-learn / PyTorch | |
| **快 JSON** | orjson / ujson | 比标准库 `json` 快 |
| **任务队列** | Celery / rq / dramatiq | 分布式/延迟任务 |
| **缓存/MQ 客户端** | redis-py / confluent-kafka | |
| **迭代/函数增强** | more-itertools / toolz / boltons | 补 `itertools`/`functools` |

> **Guava/Lombok 对照**:Java 的 Guava(集合/缓存/字符串)≈ Python 的 `collections`+`itertools`+`more-itertools`+`toolz`;Lombok(数据类/Builder)≈ `dataclasses`/`attrs`/`pydantic`;Guava Cache ≈ `functools.lru_cache`/`cachetools`。

资深选型直觉:**能用标准库就用标准库**(`collections`/`pathlib`/`itertools` 已经很强);数据边界要校验上 `pydantic`;HTTP 用 `httpx`;Web 用 `FastAPI`+`SQLAlchemy`;数据分析 `pandas`+`numpy`。

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 标准库定位 | Java 标准库 + Guava 补;Go 标准库强 | "batteries included",标准库极全 |
| 集合工具 | Guava / `java.util` | `collections`(`Counter`/`deque`/`defaultdict`) |
| 路径/IO | `java.nio.file.Path`、`os` | `pathlib`(用 `/` 拼)、`shutil` |
| 时间 | `java.time`(ZonedDateTime) | `datetime` + `zoneinfo`(优先 aware) |
| 日志 | SLF4J/Logback | `logging`(入口配一次,模块 `getLogger(__name__)`) |
| 数据类 | record / Lombok | `dataclasses` / `attrs` / `pydantic` |

## 章末面试卡

**Q1. `defaultdict` 和普通 dict 的 `setdefault` 比有什么好处?`Counter` 干什么?**
`defaultdict(factory)` 在访问缺失键时自动用 `factory()` 建默认值,省去 `if k in d` / `setdefault` 样板,适合分组累加。`Counter` 是计数专用 dict,`most_common(n)` 直接给出频次最高的 n 项。

**Q2. `deque` 和 `list` 区别?什么时候用 `deque`?**
`deque` 是双端队列,两端 append/pop 都是 O(1);`list` 头部插入/删除是 O(n)。需要队列(FIFO)或频繁在头部增删时用 `deque`,而不是 `list.pop(0)`。

**Q3. 为什么推荐 `pathlib` 而不是 `os.path`?**
`pathlib.Path` 面向对象:用 `/` 运算符拼路径、`.name/.suffix/.parent` 取部件、`.read_text()/.exists()` 直接操作,比 `os.path.join` + 字符串拼接 + `open` 更可读、跨平台更稳。新代码首选。

**Q4. Python 里怎么处理时区?用什么库?**
用带时区(aware)的 `datetime` + 标准库 `zoneinfo`(3.9+,`ZoneInfo("Asia/Shanghai")`),不再需要第三方 `pytz`。避免用裸 naive 时间做跨时区运算。

**Q5. `logging` 该怎么用?和 `print` 比?**
生产用 `logging` 不用 `print`:支持级别、格式、多输出目标、按模块分类。每个模块 `logging.getLogger(__name__)`,只在**应用入口**配置一次 handler/level,别在库模块顶层配置。

**Q6. 需要做数据校验/序列化,标准库够吗?**
简单数据类 `dataclasses` 够;但要**运行时校验、类型转换、从 JSON 解析**(如 API 入参),用 **pydantic**——它读类型注解做校验,是 FastAPI 等框架的基础。
