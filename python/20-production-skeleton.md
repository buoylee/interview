# 19 · 实战骨架:从语法到能上线

> **为什么这章重要**:前面教的是"语言",这章教"怎么把语言组织成一个能上线的服务"——项目结构、配置与密钥、生产级日志、错误边界。这是从"会写 Python"到"能交付 Python 项目"的那一跃,也是面试聊"你怎么组织一个项目"时的底气。框架专题(FastAPI 等)在 [`../fastapi-ops/`](../fastapi-ops/);这里讲与框架无关的工程骨架。

## 一、项目结构(src layout)

```
myservice/
├── pyproject.toml          # 依赖、元数据、工具配置(第 11 章)
├── uv.lock                 # 锁文件,提交
├── .env.example            # 配置样例(提交);真正的 .env 不提交
├── .gitignore              # 含 .venv/ .env __pycache__/
├── src/
│   └── myservice/
│       ├── __init__.py
│       ├── config.py       # 配置集中处
│       ├── logging.py      # 日志配置
│       ├── main.py         # 入口:if __name__ == "__main__"
│       ├── api/            # 接口层
│       ├── services/       # 业务逻辑
│       └── repositories/   # 数据访问
└── tests/
    ├── conftest.py
    └── test_*.py
```

原则(呼应第 10 章):**按职责分层、模块单一职责、文件别太大**;用 src layout 强制"按安装后的样子导入";配置/日志各自集中一处,别散落。

## 二、配置与密钥:12-factor 的核心一条

**配置从环境读,不写死在代码里**(12-factor App 的 "Config" 原则)。同一份镜像/代码,靠环境变量在 dev/staging/prod 切换,密钥永不进代码库。

### 基线:`os.environ`

```python
import os
port = int(os.environ.get("APP_PORT", "8000"))          # 带默认 + 类型转换
debug = os.environ.get("DEBUG", "false").lower() == "true"
db_url = os.environ["DATABASE_URL"]                      # 必需项:缺了就该启动失败
```

`os.environ[key]` 缺失会 `KeyError`(对必需配置是好事——**fail fast**,别让服务带着空配置裸奔);可选项用 `.get(key, default)`。

### 推荐:`pydantic-settings`(类型化、带校验、自动读 env)

```python
# 需 pip install pydantic-settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_port: int = 8000           # 自动从环境变量 APP_PORT 读,并转成 int
    debug: bool = False
    database_url: str              # 无默认 = 必需,缺失启动即报错
    model_config = {"env_file": ".env"}

settings = Settings()              # 启动时一次性加载 + 校验
```

好处:配置**有类型、有校验、有默认、集中声明**,缺必需项启动就炸而不是运行到一半才炸。这是 FastAPI 生态的标配。

### `.env` 文件

本地开发把环境变量放 `.env`(`DATABASE_URL=...`),用 `python-dotenv` 或 pydantic-settings 的 `env_file` 加载。**`.env` 必须进 `.gitignore`**;仓库里放一份不含真值的 `.env.example` 告诉别人需要哪些变量。

> 密钥(API key、DB 密码)同理:**绝不硬编码、绝不进 git**(第 19 章)。生产从环境变量或密钥管理服务(Vault/云 KMS/Secrets Manager)注入。

## 三、生产级日志

第 14 章讲了 `logging` 基础,生产再加几条:

```python
import logging.config

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "std": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "std"},
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

log = logging.getLogger("myservice.payment")    # 按模块命名,形成层级
log.info("订单已创建", extra={"order_id": 123})
```

生产要点:

- **集中用 `dictConfig` 配置一次**(在应用入口),而不是每个模块 `basicConfig`(第 10 章)。
- **按 `__name__`/模块路径命名 logger**,形成 `myservice.payment` 这样的层级,便于分模块调级别。
- **日志输出到 stdout/stderr**(12-factor:把日志当事件流,由运行环境收集),容器化部署别自己写文件轮转。
- **结构化日志**:生产多用 JSON 日志(`structlog`/`python-json-logger`),便于 ELK/Loki 检索。
- **记异常带堆栈**用 `log.exception(...)`(在 `except` 块里),它自动附上 traceback:

```python
try:
    charge(order)
except PaymentError:
    log.exception("扣款失败")     # 自动带完整堆栈,排错关键
    raise
```

- **别 `print` 调试上线**;别把密钥/PII 写进日志。

## 四、错误边界

不是每处都 `try`,而是想清楚"异常在哪一层被处理":

- **底层/纯逻辑**:让异常自然抛出,别就地吞掉(吞了上层就瞎了)。
- **边界层**(API handler、任务消费者、CLI 入口):在这里**统一捕获**,转成对用户友好的响应/退出码,并 `log.exception` 记录根因。
- **fail fast**:配置缺失、依赖不可用这类"启动就注定跑不了"的问题,**启动时就崩**,别拖到第一个请求。
- **别用裸 `except:`**(第 08 章),别吞掉异常只 `pass`;包装异常保留链(`raise X from e`)。

```python
# API 边界统一处理(伪代码)
def handle(request):
    try:
        return service.process(request)
    except ValidationError as e:
        return error_response(400, str(e))      # 预期错误 → 4xx
    except Exception:
        log.exception("未处理异常")             # 意外错误 → 记堆栈 + 5xx
        return error_response(500, "internal error")
```

## 五、12-factor 速记(后端通用)

挑与 Python 最相关的几条:**配置进环境**(本章二)、**依赖显式声明 + 锁定**(第 11 章)、**日志作事件流到 stdout**(本章三)、**进程无状态**(状态进 DB/缓存,别存进程内存——尤其多 worker 各进程独立,第 10 章)、**开发/生产尽量等价**。把这几条做到,服务就具备了可部署、可水平扩展的基础。

## Java/Go 对照框

| 关注点 | Java(Spring) / Go | Python |
|--------|--------------------|--------|
| 配置 | `application.yml`/`@Value`、Go flag/env | `os.environ` / pydantic-settings + `.env` |
| 密钥 | 外部化配置 / Vault | 环境变量 / 密钥服务,**不进 git** |
| 日志 | SLF4J/Logback、`slog` | `logging` + `dictConfig`,结构化用 structlog |
| 依赖注入 | Spring 容器 | 工厂函数 / 显式传参 / `lifespan`(轻量,少用重 DI) |
| 项目骨架 | Maven 标准目录 | src layout + 分层模块 |
| 错误边界 | `@ControllerAdvice` 全局处理 | 在 API/任务/CLI 入口统一 try |

差异:Java 习惯重量级 DI 容器,Python 社区更偏**显式**——工厂函数建依赖、启动生命周期里装配,而非到处 `@Autowired`。配置/日志/12-factor 的思路两边一致。

## 章末面试卡

**Q1. 配置应该怎么管?为什么不写在代码里?**
按 12-factor,配置从**环境变量**读(`os.environ` 或 pydantic-settings),代码与配置分离:同一份代码靠环境在 dev/prod 切换,密钥不进代码库。必需配置缺失应**启动即失败**(fail fast),可选项给默认值。

**Q2. 密钥(API key/密码)怎么管?**
绝不硬编码、绝不提交进 git;本地放 `.gitignore` 的 `.env`,生产从环境变量或密钥管理服务(Vault/云 KMS)注入。仓库只放不含真值的 `.env.example`。

**Q3. 生产日志和 `print` 调试有什么区别?要注意什么?**
用 `logging`:分级别、按模块命名 logger、入口 `dictConfig` 配一次、输出到 stdout 由环境收集、异常用 `log.exception` 带堆栈、生产多用结构化(JSON)日志便于检索;不把密钥/PII 写进日志。`print` 无级别、无结构、难管控,不用于生产。

**Q4. 异常应该在哪一层处理?**
底层让异常自然向上抛(别就地吞);在**边界层**(API handler/任务消费/CLI 入口)统一捕获,转成友好响应/退出码并 `log.exception` 记根因。启动期问题 fail fast。不要裸 `except` 或吞异常 `pass`。

**Q5. 多 worker 部署要注意什么?(呼应第 10、13 章)**
每个 worker 是独立进程、各自导入模块并初始化资源,所以连接池等要每进程建一份(放启动生命周期,别在 import 顶层);进程要无状态,会话/缓存状态放外部(Redis/DB),否则多进程间不共享、扩容即出错。

**Q6. 知道 12-factor 吗?和 Python 最相关的几条?**
配置进环境、依赖显式声明+锁定、日志作事件流输出到 stdout、进程无状态可水平扩展、开发生产等价。它让服务可部署、可扩展,是云原生/容器化部署的基础约定。
