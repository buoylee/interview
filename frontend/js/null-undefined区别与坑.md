# null vs undefined 区别与坑

## 一句话模型

- **`undefined` = "压根没有"** —— 系统给的,表示"这里从来没人放过值"
- **`null` = "故意空着"** —— 人写的,表示"我明确放了个'无'在这里"

类比:`undefined` 是房间还没装修;`null` 是装修好了但主人故意留空。

## 各自从哪冒出来

`undefined` 通常**不是写出来的,是撞上的**:

```js
let a;              // 声明没赋值 → undefined
obj.不存在的属性     // → undefined
function f(x) {}
f();                // 参数没传 → x 是 undefined
function g() {}
g();                // 函数没 return → 返回 undefined
arr[999]            // 越界 → undefined
```

`null` 只在两种地方出现:**自己写的**,或 **API 约定返回的**:

```js
document.getElementById('不存在')  // → null
'abc'.match(/\d/)                 // 不匹配 → null
JSON.parse('null')                // → null
```

## 坑(按踩到的频率排)

### 坑1: `==` 与 `===` 对它们态度不同(这是唯一该用 == 的地方)

```js
null == undefined    // true   ← 双等认为它俩相等
null === undefined   // false  ← 三等区分它俩
null == 0            // false  ← 注意! null 双等不等于 0
```

由此产生 JS 圈唯一公认的 `==` 合法用法——**一次判掉两种空**:

```js
if (x == null) { ... }   // 等价于 x === null || x === undefined
```

### 坑2: `||` 当默认值会误伤 0、''、false

```js
options.temperature || 1   // 传 0 → 被当成"没传", 变成 1 ❌
options.temperature ?? 1   // 传 0 → 得 0; 不传/null → 得 1 ✅
```

`??`(空值合并)**只把 null/undefined 当"没传"**;`||` 把所有 falsy(`0`、`''`、`false`、`NaN`)都兜了。

### 坑3: 参与运算行为完全不同

```js
null + 1          // 1    (null 转数字是 0)
undefined + 1     // NaN  (undefined 转数字是 NaN)
Number(null)      // 0
Number(undefined) // NaN
```

null 混进计算 → 得到**悄悄错的数**;undefined 混进计算 → 得到 **NaN 一路传染**。

### 坑4: JSON.stringify 丢 undefined、保留 null

```js
JSON.stringify({ a: undefined, b: null })  // '{"b":null}'  ← a 整个消失!
```

发请求体时,值为 undefined 的字段**根本不会发出去**,null 会原样发。
后端"收到 null"和"没收到这个字段"往往走不同逻辑 → 前后端联调高频坑。

### 坑5: typeof null === 'object'

```js
typeof undefined  // 'undefined'
typeof null       // 'object'   ← 1995 年留下的历史 bug, 永远不会修
```

判断"是不是对象"要写:

```js
x !== null && typeof x === 'object'
// 或者惯用短路: if (x && typeof x === 'object') { ... }
```

### 坑6: 函数默认参数只认 undefined, 不认 null

```js
function f(x = 10) { return x; }
f(undefined)  // 10   ← 默认值生效
f(null)       // null ← 默认值不生效!
```

### 坑7 (TS 限定): `?` 可选属性是 undefined, 不是 null

```ts
interface Opts { name?: string }   // 类型是 string | undefined
```

TS 里两者类型不互通:`string | null` 塞给要 `string | undefined` 的地方会报错。
所以 TS 项目通常约定**只用其中一个**表达"空"(常见: 业务层只用 undefined, null 只出现在 API 边界)。

## 实战守则(记这三条就够)

1. **判空一律 `x == null` 或 `x ?? 默认值`** —— 两种空一起处理,不纠结到底是哪种
2. **默认值用 `??` 别用 `||`** —— 除非明确想把 `0`/`''`/`false` 也兜掉
3. **自己赋空值统一用 null**(或干脆不赋) —— 看到 null 就知道是人放的,看到 undefined 就知道是漏了,排查方向立刻清晰
