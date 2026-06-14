# 11 · 工程化:环境、依赖、打包、工具链

> **为什么这章重要**:从 Java/Go 过来,最让人迷路的不是语法,而是 Python 的工程化生态——它**碎片化**,没有 Maven/`go.mod` 那种"官方唯一答案"。环境隔离、依赖锁定、打包发布、lint/format 各有好几套工具。这章给你一张现代(2025)地图:用什么、为什么、和你熟的对应物是什么。

## 一、虚拟环境:先解决"装哪儿"

Python 默认把包装到全局,多个项目共享会版本打架。**虚拟环境**给每个项目一个独立的包目录:

```bash
python3 -m venv .venv          # 在项目下建虚拟环境
source .venv/bin/activate      # 激活(Windows: .venv\Scripts\activate)
python -m pip install requests # 此后装的包只进 .venv,不污染全局
deactivate                     # 退出
```

激活后 `python`/`pip` 指向 `.venv` 里的那份。`.venv/` 要加进 `.gitignore`(不提交)。这是最基础的方案,Java/Go 没有对应物——它们靠 `~/.m2`、模块缓存 + 版本号隔离,Python 则是物理隔离一个目录。

## 二、依赖管理:从 pip 到现代工具

### pip + requirements.txt(传统,有局限)

```bash
pip install requests
pip freeze > requirements.txt   # 导出当前所有包及版本
pip install -r requirements.txt # 别处复现
```

局限:`requirements.txt` 把直接依赖和间接依赖混在一起、不区分"我要的"和"被带进来的";没有真正的**锁文件**机制保证跨机器**逐字节可复现**;不解决"开发依赖 vs 运行依赖"。

### 现代方案:uv(推荐)/ poetry / pdm

它们统一管理"声明依赖 → 解析 → 锁定 → 安装",并把元数据集中到 `pyproject.toml`:

- **uv**(Rust 写的,2024 起爆火):极快,一个工具管虚拟环境 + 依赖 + 锁文件,正在成为事实标准。
  ```bash
  uv init myproj && cd myproj    # 建项目(含 pyproject.toml)
  uv add requests                # 加依赖,自动更新 pyproject + uv.lock
  uv run python app.py           # 在项目环境里运行(自动建/同步 .venv)
  uv sync                        # 按锁文件复现环境
  ```
- **poetry**:更早流行,功能全(依赖/打包/发布一条龙),`poetry add`/`poetry install`,锁文件 `poetry.lock`。
- **pdm**:类似 poetry,标准化程度高。

共同点:**锁文件**(`uv.lock`/`poetry.lock`)记录整棵依赖树的精确版本与哈希,保证"我的机器和 CI 装出来的一模一样"——这才是 Java `pom.xml` + 中央仓库、Go `go.sum` 给你的那种可复现性。**锁文件要提交进 git。**

## 三、`pyproject.toml`:统一的项目清单

现代 Python 项目的核心配置文件(PEP 621),取代了散落的 `setup.py`/`setup.cfg`/各种 `.cfg`。它声明项目元数据、依赖、构建后端,还能集中放工具配置:

```toml
[project]
name = "myproj"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff", "mypy"]   # 开发依赖,与运行依赖分开

[build-system]
requires = ["hatchling"]                 # 构建后端(也可 setuptools/poetry-core)
build-backend = "hatchling.build"

[tool.ruff]                              # 工具配置也集中在这
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
```

一个文件管完依赖、打包、工具配置——对比 Maven 的 `pom.xml` 但更轻、更声明式。

## 四、打包与发布

把项目打成可分发的产物:

- **sdist**(`.tar.gz`):源码分发,安装时在目标机构建。
- **wheel**(`.whl`):预构建的二进制分发,**装得快**(无需在目标机编译),现代首选。

```bash
python -m build          # 产出 dist/*.whl 和 dist/*.tar.gz
python -m twine upload dist/*   # 发布到 PyPI(或用 uv/poetry 自带的 publish)
```

wheel 之于 Python ≈ jar 之于 Java(预打包、直接用)。日常装包之所以快,多半是因为拿到的是 wheel 而非现场编译 sdist。

## 五、质量工具链

| 工具 | 干什么 | 取代了 |
|------|--------|--------|
| **ruff** | lint + format,极快(Rust) | flake8 + black + isort + pyupgrade 一把梭 |
| **mypy** / pyright | 静态类型检查([第 09 章](09-typing.md)) | — |
| **pre-commit** | git 提交前自动跑上面这些 | 手动检查 |

```bash
ruff check .          # 查问题(未用变量、import 顺序、风格…)
ruff check --fix .    # 自动修可修的
ruff format .         # 格式化(等价 black)
mypy src/             # 类型检查
```

`ruff` 是近年最大的提效:一个工具几秒扫完过去要 flake8+black+isort 几十秒的活,生产项目几乎都在迁。配上 `pre-commit`,提交前自动拦下风格/类型问题。

## 六、项目布局:src layout

```
myproj/
├── pyproject.toml
├── uv.lock
├── src/
│   └── myproj/          # ← 包放在 src/ 下(src layout)
│       ├── __init__.py
│       └── core.py
└── tests/
    └── test_core.py
```

**src layout**(包放在 `src/` 子目录)比"包直接放根目录"(flat layout)更稳妥:它强制你"像外部用户一样**安装后**导入",避免"测试时不小心导入了源码目录而非已安装包"导致的诡异问题。现代脚手架(uv/poetry)默认或推荐 src layout。

## Java/Go 对照框

| 关注点 | Java | Go | Python |
|--------|------|-----|--------|
| 环境隔离 | `~/.m2` + 版本 | 模块缓存 + 版本 | **物理虚拟环境** `.venv/` |
| 依赖声明 | `pom.xml`/`build.gradle` | `go.mod` | `pyproject.toml` |
| 锁定可复现 | 版本范围 + 仓库 | `go.sum`(内建) | `uv.lock`/`poetry.lock`(需工具) |
| 构建产物 | jar/war | 单一静态二进制 | wheel(`.whl`)/ sdist |
| lint/format | Checkstyle/Spotless | `gofmt`(内建统一) | ruff(社区收敛中) |
| 官方唯一方案 | 基本是(Maven/Gradle) | 是(`go` 命令一把抓) | **没有**,生态碎片化 |

最大痛点就是最后一行:Go 的 `go` 命令、Java 的 Maven 几乎是唯一答案;Python 历史上 pip/virtualenv/pipenv/poetry/pdm/conda 群雄并起。**2025 年的务实选择:新项目直接上 `uv`**(快、一体化、正在收敛成事实标准),老项目看现状用 pip/poetry。

## 章末面试卡

**Q1. 虚拟环境是干什么的?为什么需要?**
给每个项目独立的包安装目录,避免不同项目的依赖版本在全局互相冲突。`python -m venv .venv` 创建,激活后 `pip`/`python` 都指向它。Java/Go 靠仓库 + 版本号隔离,Python 用物理目录隔离。

**Q2. `requirements.txt` 和锁文件(lock)有什么区别?**
`pip freeze` 出的 `requirements.txt` 把直接/间接依赖混在一起、不保证跨机器逐字节一致;锁文件(`uv.lock`/`poetry.lock`)记录整棵依赖树的精确版本 + 哈希,保证可复现安装,类似 `go.sum`。锁文件应提交。

**Q3. sdist 和 wheel 有什么区别?**
sdist 是源码分发(`.tar.gz`,装时可能要在目标机构建);wheel 是预构建二进制分发(`.whl`,装得快、无需编译),现代首选。wheel ≈ Java 的 jar。

**Q4. `pyproject.toml` 是什么?取代了什么?**
现代 Python 项目的统一配置文件(PEP 621):声明项目元数据、依赖、构建后端,并集中各工具(ruff/pytest/mypy)的配置。取代了过去的 `setup.py`/`setup.cfg` 等散乱文件。

**Q5. ruff 是什么?为什么大家在迁?**
Rust 写的极速 lint + format 工具,一个工具替代 flake8 + black + isort + pyupgrade 等一整套,速度快几十倍。配 pre-commit 可在提交前自动检查/修复。

**Q6. Python 依赖管理为什么比 Java/Go 乱?现在该用什么?**
历史上没有官方唯一方案,pip/virtualenv/pipenv/poetry/pdm/conda 并存,各管一段。2025 的务实选择:新项目用 `uv`(快、一体化管环境+依赖+锁文件,正成事实标准),既有项目沿用 pip/poetry。
