# 18 · 安全基础

> **为什么这章重要**:资深工程师要能识别"这行代码有没有安全隐患"。Python 几个特性是双刃剑——`eval`/`exec`/`pickle` 能执行任意代码,字符串拼接能造成注入,用错随机数会泄密。这章覆盖语言级危险动作 + 常用加密原语 + 输入校验心智,也是越来越常见的面试维度。

## 一、绝不对不可信输入用 `eval` / `exec`

`eval`(求值表达式)和 `exec`(执行语句)会**运行字符串里的代码**:

```python
eval("1 + 1")          # 2 —— 看着无害
eval(user_input)       # 灾难 —— 用户传 "__import__('os').system('rm -rf /')" 就执行了
```

对不可信输入用它们 = 把执行权交给对方(RCE)。**需要"把字符串变数据"用安全替代**:

- 解析字面量(list/dict/数字/字符串)→ `ast.literal_eval`(只认字面量,不执行代码):
  ```python
  import ast
  ast.literal_eval("[1, 2, {'a': 3}]")   # 安全;遇到函数调用等会直接报错
  ```
- 解析配置/数据 → JSON / TOML / YAML(`yaml.safe_load`,别用 `yaml.load`)。

记住:**看到 `eval`/`exec` 接触外部输入就是红灯。**

## 二、pickle 反序列化(回顾)

如[第 18 章](18-io-and-serialization.md)所讲,`pickle.loads` 反序列化时会执行还原代码,**对不可信数据 `loads` = RCE**:

```python
class Evil:
    def __reduce__(self):
        return (__import__("os").system, ("whoami",))
# pickle.loads(攻击者数据) 会执行 os.system(...)
```

同类的还有 `yaml.load`(用 `yaml.safe_load`)、`shelve`、`jsonpickle` 等。**反序列化不可信数据一律视为执行对方代码**;对外交换用 JSON。

## 三、注入:别用字符串拼接构造命令/查询

### SQL 注入

```python
# ❌ 危险:用户输入直接拼进 SQL
cur.execute(f"SELECT * FROM users WHERE name = '{name}'")
#   name = "x'; DROP TABLE users; --"  → 拖库

# ✅ 参数化查询:占位符,驱动负责转义
cur.execute("SELECT * FROM users WHERE name = %s", (name,))
```

**永远用参数化查询/绑定变量**(`%s`/`?`/`:name`,视驱动而定),让数据库驱动处理转义,而不是自己拼字符串。ORM(SQLAlchemy)默认就是参数化的。

### 命令注入

```python
import subprocess
# ❌ 危险:shell=True + 拼接,用户输入能注入 shell 命令
subprocess.run(f"ping {host}", shell=True)
#   host = "x; rm -rf /"  → 执行了 rm

# ✅ 传参数列表 + 不用 shell
subprocess.run(["ping", "-c", "1", host])   # host 作为单个参数,不经 shell 解析
```

规则:**`subprocess` 用参数列表、避免 `shell=True`**;非要 shell 时对输入用 `shlex.quote`。

### 路径穿越

拼用户提供的文件名时,警惕 `../../etc/passwd`。用 `pathlib` 解析后校验是否仍在允许目录内(`Path(base, name).resolve()` 后检查 `.is_relative_to(base)`)。

## 四、加密原语:用对标准库

### 哈希:`hashlib`

```python
import hashlib
hashlib.sha256(b"hello").hexdigest()    # 通用摘要(校验完整性、指纹)
```

⚠️ **存密码不要用裸 `sha256`/`md5`**——它们太快,易被暴力/彩虹表破解。密码要用**慢哈希 KDF** 加盐:

```python
# 标准库的 pbkdf2(生产更推荐 bcrypt/argon2 这类专用库)
dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
```

### 安全随机:`secrets`,不是 `random`

```python
import secrets, random

secrets.token_hex(16)        # 密码学安全的随机 token(密钥、会话 ID、重置令牌)
secrets.token_urlsafe(16)    # URL 安全版

random.seed(42)
random.random()              # 0.6394...  ← 可复现 = 可预测!
```

**`random` 是伪随机、可预测(给同样 seed 出同样序列),绝不能用于安全场景**(token/密码/密钥)。任何"需要别人猜不到"的随机值用 `secrets`(或 `os.urandom`)。`random` 只用于模拟、洗牌、采样这类非安全用途。

### 比较签名:`hmac.compare_digest` 防时序攻击

```python
import hmac, hashlib
expected = hmac.new(key, msg, hashlib.sha256).hexdigest()
hmac.compare_digest(expected, received)    # 定长时间比较,别用 == 比 token/签名
```

普通 `==` 比较字符串会**短路**(第一个不同字符就返回),攻击者能借响应时间差逐字节猜出 token。比对密钥/签名/token 用 `hmac.compare_digest`(恒定时间)。

## 五、输入校验与密钥管理

- **校验用显式判断,别用 `assert`**:`assert` 在 `python -O` 下被跳过(第 08 章),拿它当安全/输入校验等于生产没校验。用 `if not valid: raise ValueError(...)`,或在边界用 **pydantic** 做结构化校验。
- **密钥别硬编码、别进 git**:从环境变量/密钥管理服务读(第 20 章),`.env` 加进 `.gitignore`。源码里出现 `API_KEY = "sk-..."` 是事故常客。
- **最小权限 + 不信任输入**:所有外部输入(请求、文件、环境)默认不可信,先校验再用。

## Java/Go 对照框

| 风险 | Java / Go 对应 | Python |
|------|----------------|--------|
| 反序列化 RCE | Java 原生序列化漏洞 | `pickle.loads`/`yaml.load` 不可信数据 |
| 动态执行 | 反射/脚本引擎 | `eval`/`exec`(用 `ast.literal_eval` 替代) |
| SQL 注入 | PreparedStatement | 参数化查询(`%s`/`?`),别拼字符串 |
| 命令注入 | `ProcessBuilder` 列表传参 | `subprocess` 列表传参、避免 `shell=True` |
| 安全随机 | `SecureRandom` vs `Random` | `secrets`/`os.urandom` vs `random` |
| 时序安全比较 | `MessageDigest.isEqual` | `hmac.compare_digest` vs `==` |

逻辑和你熟的 Java 几乎一一对应——`SecureRandom` vs `Random` ≈ `secrets` vs `random`,PreparedStatement ≈ 参数化查询,反序列化漏洞两边同病。

## 章末面试卡

**Q1. `eval`/`exec` 有什么风险?怎么安全地把字符串转成数据?**
它们执行字符串中的任意代码,对不可信输入即 RCE。把字符串解析成数据用 `ast.literal_eval`(只认字面量、不执行)或 JSON/`yaml.safe_load`,绝不对外部输入用 `eval`/`exec`。

**Q2. 为什么存密码不能用 `sha256`?该用什么?**
`sha256`/`md5` 计算太快,易被暴力破解和彩虹表攻击。密码要用**加盐的慢哈希 KDF**:标准库 `hashlib.pbkdf2_hmac`,生产更推荐 bcrypt/argon2 专用库。

**Q3. `random` 和 `secrets` 区别?什么时候必须用 `secrets`?**
`random` 是可预测的伪随机(同 seed 同序列),只适合模拟/采样;`secrets`(及 `os.urandom`)是密码学安全随机。任何"别人不能猜到"的值——token、会话 ID、密钥、重置令牌——必须用 `secrets`。

**Q4. 比较 token/签名为什么不能用 `==`?**
普通 `==` 会短路(遇到第一个不同字符即返回),比较耗时随匹配前缀长度变化,攻击者可借时序差逐字节爆破。用 `hmac.compare_digest` 做恒定时间比较。

**Q5. 怎么防 SQL / 命令注入?**
SQL:用参数化查询/绑定变量(`execute(sql, params)`),让驱动转义,别用 f-string 拼 SQL;ORM 默认参数化。命令:`subprocess` 传**参数列表**而非字符串、避免 `shell=True`,必要时 `shlex.quote`。

**Q6. 为什么不能用 `assert` 做输入/权限校验?**
`python -O`(优化模式)会**移除所有 `assert`**,导致生产环境校验直接消失。安全/输入校验必须用显式 `if ... raise`(或 pydantic),`assert` 只用于开发期捕捉内部不变量。
