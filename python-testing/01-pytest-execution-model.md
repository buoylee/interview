# pytest 执行模型

## 核心问题

pytest 的红灯不都来自测试函数。配置可能在启动阶段选错，模块可能在 collection 阶段导入失败，fixture 可能在 setup 或 teardown 失败，plugin 还可能改变收集与报告。若只看最后一行 `ERROR`，团队很容易在错误层修复问题，例如把 `sys.path` 修改塞进测试，掩盖 CI 没有安装被测包的事实。

本章建立一个可诊断的模型：先确定 pytest 当前处于哪个阶段，再沿 node ID、导入身份和 hook 来源缩小范围。它解释 pytest 机制，不增加订单服务生产行为；唯一新增测试是默认不收集、必须显式运行的 assertion failure 场景。

## 直觉模型

### 一次运行是两条相交的链

第一条是启动与执行时间线：

`配置发现 → plugin/conftest 加载 → collection/import → setup → call → teardown → report`

第二条是 collection tree。便于记忆的主干是 `Session → Package/Module/Class → Function`：`Session` 是整次运行的根；目录是 Python package 时可产生 `Package` collector；测试文件产生 `Module`；测试类可产生 `Class`；最终可执行叶子通常是 `Function` item。实际树还可能包含目录和第三方 collector，不能把这条主干误当成所有项目都固定出现每一层。

collector 负责发现子节点，item 才是可执行叶子。node ID 是从 `rootdir` 出发的稳定地址，典型语法是 `path/to/test_file.py::TestClass::test_method[param-id]`。文件、类、函数和参数化 case 都能成为选择边界；本章场景的地址是 `scenarios/collection/test_assertion_report.py::test_assert_rewrite_shows_both_operands`。pytest 官方配置文档说明 `rootdir` 用于构造 node ID 和保存运行状态，但**不会**修改 `sys.path` 或 `PYTHONPATH`。[pytest configuration](https://docs.pytest.org/en/stable/reference/customize.html#initialization-determining-rootdir-and-configfile)

### collection 不等于 execution

collection 会遍历候选路径、加载适用的 `conftest.py`、导入测试模块并把符合命名规则的对象变成 nodes。`--collect-only` 到这里停止：它仍会导入测试模块，所以导入副作用和 `ModuleNotFoundError` 仍会发生，但测试函数体不会执行。执行阶段才对每个 item 运行 fixture setup、test call 和 teardown。

因此先给失败归相位：

| 现象 | 最可能阶段 | 第一份证据 |
|---|---|---|
| `unrecognized arguments`、未知配置 | 启动／配置 | 完整 header、`pytest --help`、`--trace-config` |
| `collected 0 items` | collection | `rootdir`、`configfile`、`testpaths`、命名规则 |
| `ERROR collecting ...` | collection/import | 首个 import traceback、import mode、安装状态 |
| `ERROR at setup` / teardown error | fixture 生命周期 | `--setup-show` 与 fixture traceback |
| `FAILED ...` | test call 或报告 | node ID、assertion diff、`--tb` 输出 |

## 机制深入

### rootdir、配置发现与 testpaths

pytest 先结合命令行路径和向上搜索到的配置文件确定 `rootdir` 与 `configfile`；候选配置不会合并，命中的配置决定本次运行约定。这里有两个不同的版本节点：pytest 8.1 起，在没有找到其他配置时，不含旧式 `[tool.pytest.ini_options]` 的 `pyproject.toml` 也可成为兜底 `configfile`；pytest 9 另行增加了原生 `[tool.pytest]` 配置表支持。因此诊断时要读实际 header，不要根据当前 shell 目录猜配置。[pytest configuration discovery](https://docs.pytest.org/en/stable/reference/customize.html#finding-the-rootdir)

未传测试路径时，pytest 在从 `rootdir` 运行的常规场景使用 `testpaths`。本 lab 在 `pyproject.toml` 固定 `testpaths = ["tests"]`，所以 `scenarios/collection/` 不属于默认套件；显式传入该路径则是一次有意 opt-in。这个隔离比给故意失败测试加 `xfail` 更诚实：默认绿灯代表产品套件真的通过，机制实验的红灯仍保留原始失败语义。

注意三个不同概念：工作目录影响 pytest 从哪里开始找配置；`rootdir` 给 node ID 和 cache 定锚；Python 的模块查找由 import mode、package 布局和环境中的安装决定。把三者混为一谈，最常见的产物就是脆弱的 `sys.path.insert(...)`。

### import mode 与 sys.modules

pytest 9 的官方导入说明列出三种模式：[pytest import mechanisms](https://docs.pytest.org/en/stable/explanation/pythonpath.html#import-modes)

| import mode | 测试模块如何导入 | 主要取舍 |
|---|---|---|
| `prepend`（默认） | 把包含测试模块的目录放到 `sys.path` 前部，再用标准导入 | 非 package 测试文件必须全局同名唯一；本地源码可能遮蔽已安装包 |
| `append` | 把目录放到 `sys.path` 尾部，再用标准导入 | 较容易针对已安装包运行，但非 package 测试仍有同名约束 |
| `importlib` | pytest 用 importlib 直接导入测试模块，不为此改 `sys.path` | 根据相对 `rootdir` 的路径生成唯一模块名；测试模块不能依赖“测试目录被塞进路径”来互相导入 |

Python 每个模块身份都进入 `sys.modules`。在 `prepend`／`append` 下，两个非 package 目录若都有 `test_api.py`，它们竞争同一个顶层模块名，pytest 会报告 import mismatch 或 collection error；加 package 边界可保留完整模块名。`importlib` 会生成基于路径的唯一名字并写入 `sys.modules`，解决 basename 冲突，却不会把任意测试 helper 变得可导入。

本项目使用 src layout，并通过 `uv sync --extra dev` 做 editable install。测试应该 `import order_service`，而不是依赖仓库根碰巧在路径上。若切换 import mode 才能让业务包出现，说明安装或布局契约还没有被修好。

### assertion import hook 与 rewritten .pyc

pytest 在启动早期安装 assertion rewriting import hook：模块导入前修改其 AST，再编译为 bytecode，于是普通 `assert got == expected` 能在失败报告里展开 operands。默认边界是被 collection 发现的测试模块和 plugin 模块；普通支持模块不会自动重写。需要更丰富报告的 helper 必须在**首次导入之前**调用 `pytest.register_assert_rewrite(...)`。pytest 会尽可能缓存带 pytest 标记的 rewritten `.pyc`；只读文件系统无法写 cache 时仍可重写，只是不能落盘。[pytest assertion rewriting](https://docs.pytest.org/en/stable/how-to/assert.html#assertion-introspection-details)

本场景的支持模块内容如下，逐字来自 [`lab/scenarios/collection/helpers.py`](lab/scenarios/collection/helpers.py)：

```python
from decimal import Decimal


def assert_total(got: Decimal, expected: Decimal) -> None:
    assert got == expected
```

场景的本地 plugin 逐字来自 [`lab/scenarios/collection/conftest.py`](lab/scenarios/collection/conftest.py)：

```python
import pytest

pytest.register_assert_rewrite("helpers")
```

测试模块逐字来自 [`lab/scenarios/collection/test_assertion_report.py`](lab/scenarios/collection/test_assertion_report.py)：

```python
from decimal import Decimal

from helpers import assert_total


def test_assert_rewrite_shows_both_operands() -> None:
    assert_total(Decimal("9.99"), Decimal("10.00"))
```

collection 先加载该路径适用的 `conftest.py`，注册 `helpers`，随后导入测试模块；测试模块再导入 helper 时，import hook 才有机会重写其中的 assert。顺序是机制边界：若 helper 在注册前已进入 `sys.modules`，事后注册不能重写已经导入的代码。[pytest plugin assertion rewriting](https://docs.pytest.org/en/stable/how-to/writing_plugins.html#assertion-rewriting)

### conftest、marker 与 plugin/hook

`conftest.py` 是按目录作用域自动发现的本地 plugin，不是应被业务代码直接 import 的工具模块。父目录 `conftest.py` 先于更靠近测试路径的子目录文件加载；一个 item 只获得其目录和祖先目录适用的局部行为。这里的 `conftest.py` 只服务显式选择的 collection 场景，不污染默认 `tests/`。

marker 是 collection 后可供选择和 plugin 解释的元数据。`-m` 按 marker expression 选择，`-k` 按 node 名、父类等关键字的 substring expression 选择；两者都不是目录隔离的替代品。自定义 marker 应在配置中注册。本 lab 开启 `--strict-markers`，拼错 marker 会立即报错，而不是静默跳过；`--strict-config` 同理保护配置项。[pytest markers](https://docs.pytest.org/en/stable/how-to/mark.html#registering-marks)

pytest 的配置、collection、执行和报告多数由 hooks 完成。同一 hook 可以有多个 plugin 实现，概念上是 `1:N` 调用：普通实现可用 `tryfirst=True` / `trylast=True` 调整相对位置；hook wrapper 在 `yield` 前包住普通实现，并在 `yield` 后反向退出。不要根据文件名猜精确调用顺序，也不要把 `tryfirst` 理解为跨所有启动阶段的全局优先级。[pytest hook ordering](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html#hook-function-ordering-call-example)

启动时 pytest 依次处理 `-p no:name` 禁用项、内建 plugin、`-p name` 显式 plugin；随后是第三方 `pytest11` entry point 自动加载阶段，而 `PYTEST_DISABLE_PLUGIN_AUTOLOAD` 专门阻止这一阶段；再下一个独立步骤才加载 `PYTEST_PLUGINS` 指定的模块，最后加载初始 `conftest.py`。所以两台机器即使命令相同，只要安装的 plugin 集或这两个环境变量不同，collection、marker、fixture、命令行参数乃至报告都可能不同。用 `pytest --trace-config` 留下活动 plugin 证据；需要隔离诊断时，pytest 8.4+ 可用 `--disable-plugin-autoload`，但 CI 的长期修复应是锁定环境而不是永远隐藏依赖漂移。[pytest plugin discovery](https://docs.pytest.org/en/stable/how-to/writing_plugins.html#plugin-discovery-order-at-tool-startup)

## 设计取舍

### 先缩小证据，不先扩大魔法

| 目标 | 首选工具 | 它回答什么 | 不要误读为 |
|---|---|---|---|
| 看 pytest 准备执行什么 | `--collect-only -q` | node ID 集合与 collection error | “完全没有执行 Python 代码” |
| 按名字缩小 | `-k` | 名字／父节点关键字匹配后的 items | marker 语义 |
| 按治理标签缩小 | `-m` | marker expression 匹配后的 items | 测试边界自动正确 |
| 看 fixture 生命周期 | `--setup-show` | 每个 item 的 setup/teardown 次序 | 业务依赖图 |
| 调整 traceback | `--tb=short|long|line|native`、`-vv` | 栈与 assertion diff 的详细度 | 修复 collection/import |
| 看加载来源 | `--trace-config` | 内建、第三方和 conftest plugins | hook 的所有运行时状态 |

官方 CLI reference 明确区分 `--collect-only`、`-k`、`-m`、`--setup-show` 和 traceback 模式；这些开关用于控制变量，不应一次全部打开制造噪声。[pytest CLI reference](https://docs.pytest.org/en/stable/reference/reference.html#command-line-flags)

### import mode 是架构选择，不是临时止痛药

src layout + editable install 让本地和 CI 都通过安装契约拿到业务包；测试是否组织成 package 则决定测试模块身份。选择 `importlib` 可以避免测试目录进入 `sys.path` 和重复 basename，却要求共享 helper 有正常可导入位置；保留默认 `prepend` 也可以，但必须治理顶层重名和本地源码遮蔽。项目应显式验证一种模式，而不是让开发者遇到红灯后轮流试三个参数。

assertion helper 也只在报告价值足够时注册 rewriting。领域 helper 若只是返回值，普通断言放在测试里更清晰；只有像本场景这样把关键 assert 封装进共享模块，才需要扩大 rewrite 边界。不要注册整个生产包：这会让测试执行与生产 bytecode 的差异无谓扩大。

## 贯穿 lab

所有命令从 `python-testing/lab/` 执行。先验证 collection，预期退出码 `0` 且恰好一个 node ID：

```bash
uv run pytest --collect-only scenarios/collection -q
```

再显式执行该 node，预期退出码 `1`，失败发生在 test call，报告包含 `Decimal('9.99')` 与 `Decimal('10.00')`：

```bash
uv run pytest scenarios/collection/test_assertion_report.py -q
```

它是 assertion import hook 的可执行证据，不属于订单服务的 unit/component/integration 边界。恢复默认反馈时运行：

```bash
uv run pytest -q
```

持久契约是默认 suite 通过，且 `testpaths = ["tests"]` 继续排除 `scenarios/`；测试数量会随后续任务增长。Task 3 实施时的快照是 `6 passed`，不是后续章节必须维持的固定计数。完整运行契约见[场景 README](lab/scenarios/collection/README.md)。

## 故障工单

### 工单：本地单测能 import，CI collection 失败

**症状**

开发者在仓库根运行测试全部通过；CI 从 `python-testing/lab/` 执行后，在任何 test call 之前报 `ERROR collecting ...` 和 `ModuleNotFoundError`。另一条 CI job 偶尔报告同名 `test_api.py` 的 import mismatch。

**证据**

- 本地与 CI header 的 `rootdir` / `configfile` 不同，本地命中了上层配置，CI 命中 lab 的 `pyproject.toml`。
- 本地 shell 曾做过 editable install，CI 只 checkout 后直接运行；`uv sync --extra dev` 没有作为明确步骤。
- 两个非 package 测试目录都有 `test_api.py`；默认 `prepend` 把它们作为同一个顶层模块名放入 `sys.modules`。
- 改成 `--import-mode=importlib` 后重名消失，但测试又无法从测试目录直接 `import helpers`，证明原来依赖的是路径副作用。

**假设**

业务包和测试 helper 的可导入性没有由项目安装／package 布局定义，而是依赖本地工作目录、已有 editable install 和默认 import mode 对 `sys.path` 的修改。CI 的 collection 只是第一个暴露该环境漂移的阶段。

**修复**

固定从 lab 执行和读取其 `pyproject.toml`；CI 先按 committed `uv.lock` 执行 `uv sync --extra dev`；业务代码保持 src layout 并从已安装的 `order_service` 导入。对重复测试名，要么把测试目录组织成有完整模块名的 package，要么选定并持续验证 `importlib`；共享测试能力放入正常可导入的测试支持 package 或 `conftest.py` fixture。禁止用 `sys.path.insert(...)`、`PYTHONPATH=.` 或复制 helper 掩盖根因。

**regression test**

在干净环境按 CI 顺序同步后先运行 `uv run pytest --collect-only -q`，断言退出码 `0` 且 node IDs 唯一，再运行默认 fast suite。若项目决定切换 import mode，把该参数放入统一配置并加入 Python 版本矩阵；不要只在某条失败 job 临时追加。

**工单结论**

collection failure 要修模块身份与环境契约，不要修业务断言。`rootdir`、editable install、重复模块名和 import mode 是四份独立证据；只有先分开它们，才能避免本地假绿。

## Java/Go 对照

| pytest 概念 | Java / JUnit | Go | 容易误判之处 |
|---|---|---|---|
| collection tree / node ID | Engine → class → method 的 test identifier | package 枚举与 `-run` 名称 | pytest 的 Python import 本身发生在 collection，失败可早于 test call |
| `conftest.py` / plugin hooks | JUnit extension、launcher listener | `TestMain`、自定义 harness | conftest 有目录作用域且参与启动顺序，不是任意 helper |
| marker、`-m`、`-k` | tag 与 method/name filter | build tag 与 `-run` regex | marker 选择不定义真实测试边界；Go build tag 还影响编译集合 |
| assertion rewriting | assertion library／字节码 instrumentation | 显式 `if` + `t.Fatalf` | pytest 会在 import 时改写测试 bytecode，普通 helper 默认不在边界内 |

JUnit 用户常把 “class 已发现” 等同于模块可加载；pytest 中模块顶层 import 是 collection 的一部分。Go 用户则容易把 package import 的编译期确定性带入 Python；Python 的 `sys.path`、`sys.modules` 与 editable install 都会改变同一文件获得的模块身份。

## 验收与面试卡

### 验收

- 能画出 `Session → Package/Module/Class → Function`，并说明 collector、item 与 node ID 的关系。
- 能区分启动／配置、collection/import、setup、call、teardown 和 report 的失败。
- 能解释 `rootdir` 为什么影响 node ID 却不负责修改 `sys.path`。
- 能比较 `prepend`、`append`、`importlib` 对 package、重复模块名与 `sys.modules` 的影响。
- 能说明 assertion rewriting 的 import hook、支持模块边界、注册时机与 rewritten `.pyc` cache。
- 能用 `--trace-config` 与 hook ordering 检查 plugin 环境差异，而不弱化 strict marker/config。
- 显式场景稳定红，默认 suite 稳定绿；两者都保留各自需要的证据。

检查机制锚点：

```bash
rg -n "Session|Package|Module|Function|node ID|assert rewriting|import hook|rootdir|sys.modules|--collect-only|conftest|hook" python-testing/01-pytest-execution-model.md
```

### 面试卡 1：pytest 为什么在执行测试前就可能失败？

**一句话：** pytest 必须先发现配置、加载 plugin/conftest、导入测试模块并建立 collection tree，任何一步失败都早于 test call。

**深答：** 我先从 header 确认 `rootdir` 与配置，再用 `--collect-only` 复现；它只跳过 item execution，不跳过模块 import。若是 `ERROR collecting`，我检查干净环境安装、src layout、import mode、重复模块名和活动 plugins，而不是先改断言或 fixture。node ID 都没形成时，业务行为通常还没有运行。

### 面试卡 2：assert helper 为什么没有 pytest 的 operands 展开？

**一句话：** assertion rewriting 默认覆盖测试与 plugin 模块，普通 helper 必须在首次 import 前显式注册。

**深答：** pytest 的 import hook 在模块编译前改写 assert AST，并可缓存 rewritten `.pyc`。测试模块自动进入边界，普通支持模块不会；我在较早加载的 `conftest.py` 或 plugin package 初始化中调用 `pytest.register_assert_rewrite`，再导入 helper。若模块已经在 `sys.modules`，注册太晚，应该修加载顺序而不是手写冗长错误字符串。

### 面试卡 3：如何解释本地能 import、CI 不能？

**一句话：** 先比较配置锚点、安装状态和模块身份，不用 `sys.path` hack 把环境差异藏起来。

**深答：** 我保存两端的 header、`--trace-config`、依赖版本和首个 collection traceback，确认是否从同一 `rootdir` 读取同一配置、是否都完成 editable install，以及测试目录是否因默认 `prepend` 产生重名模块。然后在干净环境分别用既定 import mode 做 `--collect-only`。修复是统一 lockfile 同步、src layout 和 package/test-support 布局；只有项目明确接受其取舍时才统一切换 import mode。

完成本章后返回 [Python 测试工程 track](README.md)。后续 fixture 与 plugin 章节会继续复用这里的阶段、node ID 和加载顺序词汇。
