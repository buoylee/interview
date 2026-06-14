# 10 · 模块、包、导入系统

> **为什么这章重要**:Python 靠**模块**做第一层代码组织(类是第二层),这跟 Java"一切围绕 class/package"很不同。`import` 会执行代码、会缓存、会因写法不同而踩循环导入——理解它的机制,才能解释"为什么模块顶层别放重副作用""循环导入怎么破""`if __name__ == '__main__'` 到底在判什么"。

## 一、模块与包

- **模块(module)**:一个 `.py` 文件就是一个模块。Java 靠 `class` 组织,Python 先靠 **module** 组织、再用 class:`StringUtils.trim(s)`(Java)≈ `import string_utils; string_utils.trim(s)`(Python)。
- **包(package)**:一个含 `__init__.py` 的目录,可以嵌套成 `pkg.sub.mod`。`__init__.py` 是包被导入时执行的代码(可为空,也可在里面做"重新导出")。
- **命名空间包**:没有 `__init__.py` 的目录在 3.3+ 也能作包(namespace package),允许一个包跨多个目录拼装——但常规项目建议老老实实放 `__init__.py`,行为更可预期。

## 二、`import` 时到底发生了什么

第一次 `import mod` 时,Python 会:

1. 按 `sys.path` 查找模块(finders/loaders 机制);
2. **执行该模块的顶层代码**(从上到下跑一遍);
3. 创建模块对象,**存进 `sys.modules` 缓存**;
4. 在当前命名空间绑定名字 `mod`。

**关键:同一进程内再次 `import` 同一模块,直接复用缓存,顶层代码不会重跑。**

```python
# mod.py
print("mod.py 顶层代码执行")
VALUE = 42
def foo(): return "foo result"
```
```python
# 另一个文件
import mod          # 打印 "mod.py 顶层代码执行"
import mod          # 什么都不打印 —— 命中 sys.modules 缓存
print("mod" in sys.modules)   # True
```

### 顶层代码 ≠ 函数体

`def foo(): ...` 在导入时只执行"**定义函数**"这个动作,函数体不会自动跑;只有显式 `foo()` 才执行体。`print(...)`、`x = 1` 这种顶层语句则会在导入时立即执行。

### 因此:别在模块顶层做重副作用初始化

配日志、建数据库连接池、建 Redis/HTTP client、起线程/调度器——**不要写在普通模块顶层**。因为:

- 谁 `import` 谁就触发它,初始化顺序被 import 顺序绑架;
- 副作用来源难排查;
- 测试时只想导入一个函数,也会被迫带上这些副作用。

更合理的位置:**应用启动生命周期**(FastAPI 的 `lifespan`/`startup`)、应用工厂函数、依赖注入容器、或懒加载。

```python
def create_redis_client(settings):       # 工厂函数,不在 import 时执行
    return Redis(host=settings.host, port=settings.port)

# 启动时显式创建
app.state.redis = create_redis_client(settings)
```

> **多 worker 场景**(gunicorn/uvicorn 多进程):每个 worker 是独立进程,各自走一遍导入、各自执行顶层代码。所以连接池这类资源通常**每个 worker 初始化一份**——更要放在启动生命周期里显式建,而不是 import 时偷偷建。

## 三、`__name__ == "__main__"`

每个模块都有 `__name__`:被 `import` 时它是模块名(如 `"mod"`),**被当脚本直接运行**时它是 `"__main__"`。于是这个惯用法让"既能被导入又能直接跑"成为可能:

```python
def main():
    ...

if __name__ == "__main__":   # 只有直接 python mod.py 时才进
    main()
```

实测对比同一个文件:

```
$ python3 mod.py     →  __name__ 是 "__main__"
import mod           →  __name__ 是 "mod"
```

作用:导入它时不会自动执行 `main()`(避免副作用),直接运行它时才执行。写命令行入口、可测试脚本必备。

## 四、绝对导入、相对导入、`python -m`

```python
import package.module           # 绝对导入(推荐)
from package.module import func
from . import sibling           # 相对导入(仅包内,. 当前包,.. 上层)
```

- **绝对导入**清晰、可移植,首选。
- **相对导入**只能在包内用,且**不能在被直接当脚本运行的文件里用**(那时没有包上下文,会报错)。
- **`python -m package.module`**:把目标当模块运行,会正确设置包上下文(相对导入才工作),并把当前目录加进路径。要运行包内带相对导入的入口,用 `-m` 而不是给文件路径。

## 五、循环导入

A 导入 B、B 又导入 A,就可能循环。问题出在"导入时执行顶层代码"——A 还没执行完(模块只"部分初始化"),B 反过来用 A 里还没定义好的东西,就炸:

```python
# a.py
import b
def ahello(): return "a"
b.bhello()          # a 顶层就调用 b 的函数

# b.py
import a
def bhello(): return "b"
a.ahello()          # b 顶层又回头调用 a
```
```
AttributeError: partially initialized module 'b' has no attribute 'bhello'
(most likely due to a circular import)
```

看到 **"partially initialized module"** 就是循环导入。破解办法:

1. **重构消除**(最佳):把两边共用的东西抽到第三个模块,打破环;
2. **延迟导入**:把 `import` 挪到**函数内部**,用到时才导(那时模块已初始化完);
3. **只在顶层 `import module`、在函数里才用 `module.x`**,而不是顶层 `from module import x`——后者要求导入瞬间 `x` 就已存在,更容易触发。

## 六、`__all__` 与 `from module import *`

```python
# mypkg/__init__.py
__all__ = ["foo", "Bar"]      # 控制 from mypkg import * 导出什么
from .core import foo, Bar    # “重新导出”:让外部能 from mypkg import foo
```

- `__all__` 是一个名字列表,**只影响 `from module import *`** 导出哪些名字(不影响显式导入)。
- `from module import *` 在生产代码里**不推荐**:污染命名空间、看不清名字来源。
- 包的 `__init__.py` 里做"重新导出"(把深层模块的东西提到包顶层)是常见且有用的模式,给外部一个干净的导入入口。

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 一级组织单位 | class(Java)/ package(Go) | **module**(.py 文件),class 是第二层 |
| 导入会执行代码吗 | 否(类加载是惰性、无"顶层语句") | **是**,首次导入执行模块顶层代码 |
| 重复导入 | 类只加载一次 | 模块缓存在 `sys.modules`,顶层只跑一次 |
| 循环依赖 | 编译期多能处理/报错 | 运行期"部分初始化"出 `AttributeError` |
| 入口 | `main()` / `func main()` | `if __name__ == "__main__":` |
| 可见性导出 | `public`/首字母大写 | 约定(`_私有`)+ `__all__` 控制 `import *` |

最大认知差:Java/Go 的"导入/引用"基本是声明依赖、不跑代码;**Python 的 `import` 会真的执行那个文件的顶层**。这条解释了顶层副作用、缓存、循环导入三件事的全部根源。

## 章末面试卡

**Q1. `import` 一个模块时发生了什么?会执行几次?**
首次导入:按 `sys.path` 找到模块 → **执行其顶层代码** → 创建模块对象存入 `sys.modules` → 在当前命名空间绑定名字。同进程内再次导入同一模块直接命中缓存,顶层代码**不再重复执行**。

**Q2. `if __name__ == "__main__":` 是干什么的?**
`__name__` 在模块被导入时是模块名,被当脚本直接运行时是 `"__main__"`。这个判断让文件"被导入时不自动执行入口逻辑、直接运行时才执行",既可复用又可独立跑。

**Q3. 为什么不建议在模块顶层建数据库连接/配日志?**
因为导入即执行顶层代码:谁 import 谁就触发初始化,顺序受 import 顺序绑架、副作用难排查、测试时被迫带上副作用;多 worker 下每进程都会各跑一次。应放到应用启动生命周期(`lifespan`/工厂/DI)里显式初始化。

**Q4. 循环导入为什么会报错?怎么解决?**
A、B 互相导入时,某模块还在"部分初始化"(顶层没执行完)就被对方使用其尚未定义的名字,抛 `AttributeError: partially initialized module`。解决:抽公共模块打破环、把 import 延迟到函数内部、或顶层只 `import module` 而在函数里用 `module.x`。

**Q5. `from module import *` 有什么问题?`__all__` 管什么?**
`import *` 污染命名空间、让名字来源不清,生产不推荐。`__all__` 是一个名字列表,**仅**控制 `import *` 时导出哪些名字,不影响显式导入。

**Q6. 绝对导入和相对导入怎么选?`python -m` 有什么用?**
优先绝对导入(清晰可移植);相对导入(`from . import x`)只在包内用、且不能在被直接当脚本运行的文件里用。`python -m pkg.mod` 把目标当模块运行并正确设置包上下文,是运行带相对导入的包内入口的正确方式。
