# 12 · 测试

> **为什么这章重要**:`pytest` 是 Python 测试的事实标准,它的 fixture、`parametrize`、`assert` 重写比 JUnit 那套更轻、更灵活——但范式也不同(函数 + fixture 注入,而非类 + 注解)。会写干净的测试,是资深工程师的硬指标,也是面试常聊的话题。

## 一、pytest 基础

pytest 用**普通函数 + 原生 `assert`** 写测试,不需要继承测试基类:

```python
# test_app.py —— 文件名 test_*.py / *_test.py;函数名 test_*
from app import add

def test_add():
    assert add(2, 3) == 5     # 直接用 assert
```

```bash
pytest                 # 自动发现并跑所有 test_*
pytest -q              # 安静模式
pytest test_app.py::test_add   # 只跑某个
pytest -k "add"        # 名字含 add 的测试
pytest -m "slow"       # 跑标了 @pytest.mark.slow 的
pytest -x              # 第一个失败就停
```

**`assert` 重写**是 pytest 的招牌:它在收集阶段改写你的 `assert`,失败时打印两边的实际值(`assert 5 == 6` 会告诉你左右各是多少),不像 `unittest` 要 `assertEqual`/`assertTrue` 一堆方法。

## 二、fixture:测试的依赖注入

fixture 提供测试需要的"前置数据/资源",通过**参数名注入**——测试函数声明一个和 fixture 同名的参数,pytest 自动把 fixture 的返回值传进来:

```python
import pytest

@pytest.fixture
def sample_data():
    data = {"x": 1}      # setup:准备
    yield data           # 把值交给测试(用 yield 而非 return)
    data.clear()         # teardown:测试结束后执行(yield 之后的代码)

def test_uses_fixture(sample_data):     # 参数名 = fixture 名 → 自动注入
    assert sample_data["x"] == 1
```

- **`yield` 式 fixture**:`yield` 前是 setup,`yield` 后是 teardown(无论测试成功失败都会执行),比 `setUp`/`tearDown` 更紧凑。
- **作用域 `scope`**:`function`(默认,每个测试一次)、`class`、`module`、`session`(整轮只一次,适合贵重资源如数据库连接)。
  ```python
  @pytest.fixture(scope="session")
  def db():
      conn = connect(); yield conn; conn.close()
  ```
- **`conftest.py`**:放在目录里的 fixture 共享文件,**该目录及子目录的测试自动可见这些 fixture**,无需 import。这是组织共享 fixture 的标准方式。

## 三、`parametrize`:一份逻辑,多组数据

把"同样的断言换不同输入"压成一个测试,每组数据算一个独立用例(某组失败不影响其他):

```python
@pytest.mark.parametrize("a, b, expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0),
])
def test_add(a, b, expected):
    assert add(a, b) == expected
# 跑出来是 3 个用例,失败时精确告诉你哪组挂了
```

对应 JUnit 的 `@ParameterizedTest` / Go 的 table-driven test,但更简洁。

## 四、断言异常与标记

```python
import pytest

def test_divide_raises():
    with pytest.raises(ZeroDivisionError):   # 断言"应该抛这个异常"
        divide(1, 0)

@pytest.mark.skip(reason="还没实现")
def test_later(): ...

@pytest.mark.skipif(sys.platform == "win32", reason="仅 Linux")
def test_unix_only(): ...

@pytest.mark.xfail(reason="已知 bug,待修")    # 预期失败,失败不算红
def test_known_bug(): ...
```

`pytest.raises` 还能配 `match=` 校验异常消息;`with pytest.raises(X) as exc:` 拿到异常对象做进一步断言。

## 五、Mock:隔离外部依赖

测试要快、要确定,就得把网络/数据库/时间这些不可控的东西**替换成假的**。`unittest.mock` 提供 `Mock`/`MagicMock`,pytest 提供 `monkeypatch`。

### `Mock`:造一个"什么属性方法都有"的假对象

```python
from unittest.mock import Mock

def test_mock_object():
    client = Mock()
    client.fetch.return_value = {"name": "Ann"}   # 预设返回值
    assert get_user_name(client, 42) == "Ann"
    client.fetch.assert_called_once_with(42)       # 断言被怎样调用
```

`Mock` 对象访问任何属性/方法都自动返回新的 Mock,可设 `return_value`/`side_effect`,并记录所有调用供 `assert_called_*` 校验。

### `patch`:在测试期间替换某个目标

```python
from unittest.mock import patch

@patch("app.requests.get")           # 把 app 模块里用到的 requests.get 换成 Mock
def test_fetch(mock_get):
    mock_get.return_value.json.return_value = {"ok": True}
    assert fetch_status() is True
```

**关键坑**:`patch` 的目标是"**被使用的地方**"而非"定义的地方"——要 patch `app.py` 里 `from requests import get` 进来的 `get`,得写 `@patch("app.get")`,不是 `@patch("requests.get")`。

### `monkeypatch`(pytest 内置 fixture)

```python
def test_monkeypatch(monkeypatch):
    monkeypatch.setattr("app.add", lambda a, b: 999)   # 临时替换
    monkeypatch.setenv("API_KEY", "test")               # 临时改环境变量
    # 测试结束自动还原,无需手动清理
```

### 何时 mock、何时别 mock

- **该 mock**:外部 IO(网络/DB/文件)、时间/随机、慢或不稳定的依赖、有副作用的调用。
- **别滥用**:别 mock 你正在测的逻辑本身;mock 太多会让测试"测的是 mock 而非真实行为",重构一碰就碎。优先测真实的纯函数,只在边界处 mock。

## 六、覆盖率与其他

```bash
pytest --cov=src --cov-report=term-missing   # 需 pytest-cov;看哪些行没覆盖
```

- **coverage / pytest-cov**:测覆盖率,但覆盖率高 ≠ 测得好(覆盖到不等于断言对)。
- **hypothesis**:属性测试——你描述"输入的性质"和"应满足的不变量",它自动生成大量随机用例去试图反例(如 `decode(encode(x)) == x` 对任意 x 成立)。
- **tox / nox**:在多个 Python 版本/环境矩阵里跑测试,发布库前常用。

## Java/Go 对照框

| | JUnit / Java | Go | pytest |
|--|--------------|-----|--------|
| 写法 | 类 + `@Test` 注解 | `func TestXxx(t *testing.T)` | 普通函数 `test_*` + 原生 `assert` |
| 断言 | `assertEquals` 等方法 | `if got != want { t.Errorf }` | 原生 `assert`(失败显示两边值) |
| 前置/后置 | `@BeforeEach`/`@AfterEach` | setup 函数 / `t.Cleanup` | fixture(`yield` 分 setup/teardown) |
| 依赖注入 | 手动 / Spring | 手动 | fixture 按参数名自动注入 |
| 参数化 | `@ParameterizedTest` | table-driven | `@pytest.mark.parametrize` |
| mock | Mockito | 接口 + 手写假实现 | `unittest.mock` / `monkeypatch` |

范式差异:JUnit 是"类 + 注解 + 继承体系",pytest 是"函数 + fixture 注入",更接近函数式、样板更少。

## 章末面试卡

**Q1. fixture 是什么?和 `setUp`/`tearDown` 有何不同?**
fixture 是 pytest 提供测试依赖(数据/资源)的机制,测试函数按**参数名**声明即自动注入。用 `yield` 式 fixture 时,`yield` 前是 setup、后是 teardown(成功失败都执行),且能设作用域(function/module/session)复用贵重资源——比固定的 `setUp`/`tearDown` 更灵活、可组合。

**Q2. `conftest.py` 有什么用?**
放共享 fixture(及插件钩子)的文件,所在目录及子目录的测试**无需 import 即可使用**其中的 fixture。是跨多个测试文件共享 setup 的标准方式。

**Q3. `@parametrize` 解决什么问题?**
把"同一逻辑、多组输入/期望"合成一个测试,每组数据生成一个独立用例,失败时精确指出哪组挂了。避免为每组数据复制粘贴一个测试函数。

**Q4. `patch` 时为什么要 patch "使用处"而不是"定义处"?**
因为 `from x import y` 会在使用方模块里绑定一个**指向 y 的本地名字**;替换原模块的 `x.y` 不会改到这个已绑定的本地名。所以要 patch `app` 里用到的那个名字(`app.y`),而不是它的来源 `x.y`。

**Q5. 什么时候应该用 mock,什么时候不该?**
该 mock:网络/数据库/文件等外部 IO、时间/随机、慢或不稳定的依赖。不该:mock 被测逻辑本身,或 mock 过度——那样测的是 mock 不是真实行为,重构极易误报。优先直接测纯函数,只在外部边界 mock。

**Q6. 覆盖率高就说明测试好吗?**
不。覆盖率只反映代码行**被执行**过,不保证**有断言验证其正确性**,也不覆盖输入空间的边界。它是辅助指标,不能替代对关键路径、边界、异常分支的有意义断言。
