# 阶段 2：第一个完整组件（1-2 天）

> **一句话定位**：通过构建一个逐步增强的 Todo 组件，在实践中自然覆盖 JSX、Props、State、事件处理、条件渲染、列表渲染——不再拆成零散的独立知识点。

---

## 目录

- [1. JSX：不是 HTML，是 JS](#1-jsx不是-html是-js)
- [2. 组件：返回 JSX 的函数](#2-组件返回-jsx-的函数)
- [3. Props：组件的输入](#3-props组件的输入)
- [4. State：组件的记忆](#4-state组件的记忆)
- [5. 事件处理](#5-事件处理)
- [6. 条件渲染](#6-条件渲染)
- [7. 列表渲染与 key](#7-列表渲染与-key)
- [8. 不可变更新](#8-不可变更新)
- [9. 组件拆分与单向数据流](#9-组件拆分与单向数据流)
- [10. State 设计原则](#10-state-设计原则)
- [11. 面试常问](#11-面试常问)
- [12. 练习](#12-练习)

---

## 1. JSX：不是 HTML，是 JS

### 1.1 JSX 是什么

```
JSX 看起来像 HTML，但本质是 JavaScript。

它是 React.createElement() 的语法糖：

  <h1 className="title">Hello</h1>

  编译后等价于：

  React.createElement('h1', { className: 'title' }, 'Hello')

  返回一个 JS 对象（虚拟 DOM 节点）：
  { type: 'h1', props: { className: 'title', children: 'Hello' } }

所以 JSX 能出现在任何 JS 能出现的地方：
  变量赋值、函数返回、条件表达式、数组 map...
```

### 1.2 JSX vs HTML 差异速查

| HTML | JSX | 为什么 |
|------|-----|--------|
| `class="box"` | `className="box"` | `class` 是 JS 保留字 |
| `for="input"` | `htmlFor="input"` | `for` 是 JS 保留字 |
| `style="color: red"` | `style={{ color: 'red' }}` | JSX 的 style 接收对象，不是字符串 |
| `onclick="fn()"` | `onClick={fn}` | 驼峰命名 + 传函数引用 |
| 可以不闭合 `<img>` `<br>` | 必须闭合 `<img />` `<br />` | JSX 语法要求 |
| 可以直接写注释 `<!-- -->` | `{/* 注释 */}` | JSX 里用 JS 注释 |

### 1.3 JSX 中嵌入 JS 表达式

```jsx
function Profile({ user }) {
  const isAdmin = user.role === 'admin'

  return (
    <div>
      {/* ① 变量 */}
      <h1>{user.name}</h1>

      {/* ② 表达式计算 */}
      <p>注册天数：{Math.floor((Date.now() - user.createdAt) / 86400000)}</p>

      {/* ③ 函数调用 */}
      <p>{user.name.toUpperCase()}</p>

      {/* ④ 三元表达式 */}
      <span>{isAdmin ? '管理员' : '普通用户'}</span>

      {/* ⑤ 模板字符串 */}
      <img src={`/avatars/${user.id}.jpg`} alt={`${user.name}的头像`} />
    </div>
  )
}

// ⚠️ {} 里只能放"表达式"（有返回值的东西）
// ❌ if/else、for、switch 是"语句"，不能直接放在 {} 里
// ✅ 三元 ? :、&&、map 是"表达式"，可以
```

### 1.4 Fragment：不想多套一层 div

```jsx
// ❌ 每个组件必须有唯一根元素
function Bad() {
  return (
    <h1>标题</h1>
    <p>内容</p>     // 报错：相邻 JSX 元素必须有根元素包裹
  )
}

// ✅ 方案 1：用 div 包裹（但 DOM 里多了一层无意义的 div）
function WithDiv() {
  return (
    <div>
      <h1>标题</h1>
      <p>内容</p>
    </div>
  )
}

// ✅ 方案 2：用 Fragment（不会渲染任何 DOM 元素）
import { Fragment } from 'react'

function WithFragment() {
  return (
    <Fragment>
      <h1>标题</h1>
      <p>内容</p>
    </Fragment>
  )
}

// ✅ 方案 3：Fragment 简写（最常用）
function WithShortFragment() {
  return (
    <>
      <h1>标题</h1>
      <p>内容</p>
    </>
  )
}
```

---

## 2. 组件：返回 JSX 的函数

### 2.1 最简组件

```jsx
// 组件 = 返回 JSX 的函数，仅此而已
function Greeting() {
  return <h1>Hello, World!</h1>
}

// ⭐ 两条关键规则：
// 1. 组件名必须大写开头（React 靠大小写区分 HTML 元素和自定义组件）
//    <div>  → HTML 元素
//    <Greeting>  → 自定义组件
//
// 2. 必须返回一个根元素（或 Fragment）
```

### 2.2 组件的渲染

```jsx
// 在其他组件中使用
function App() {
  return (
    <div>
      <Greeting />         {/* ← 像 HTML 标签一样使用 */}
      <Greeting />         {/* ← 每个实例是独立的 */}
    </div>
  )
}

// ⭐ 每次 React 渲染 <Greeting />，就是调用 Greeting() 函数
// 两个 <Greeting /> = 调用 Greeting() 两次 = 两个独立实例
```

### 2.3 从静态到动态

```
一个组件从静态到动态的演进路径：

  Step 1: 静态组件 → 只返回写死的 JSX（纯 HTML 翻译）
  Step 2: + Props   → 接受外部数据，变得可配置
  Step 3: + State   → 有自己的"记忆"，能响应交互
  Step 4: + 事件    → 用户操作触发 state 变化
  Step 5: + 拆分    → 大组件拆成多个小组件

接下来我们按这个路径构建一个 TodoApp。
```

---

## 3. Props：组件的输入

### 3.1 基本用法

```jsx
// Props = 父组件传给子组件的数据 = 函数的参数

// 定义：通过解构获取 props
function UserCard({ name, age, isOnline }) {
  return (
    <div>
      <h2>{name}（{age}岁）</h2>
      <span>{isOnline ? '🟢 在线' : '⚫ 离线'}</span>
    </div>
  )
}

// 使用：像 HTML 属性一样传值
function App() {
  return (
    <div>
      <UserCard name="张三" age={25} isOnline={true} />
      <UserCard name="李四" age={30} isOnline={false} />
    </div>
  )
}

// ⭐ props 可以是任何 JS 值：
// 字符串：name="张三"（不用 {}）
// 数字：age={25}
// 布尔：isOnline={true}（或简写 isOnline）
// 对象：user={{ name: '张三', age: 25 }}
// 数组：items={[1, 2, 3]}
// 函数：onClick={() => alert('hi')}
// JSX：icon={<Icon />}
```

### 3.2 Props 的核心规则

```
⭐ Props 是只读的

  function UserCard({ name }) {
    name = '别的名字'  // ❌ 绝对不能修改 props！
    return <h2>{name}</h2>
  }

  为什么？
  → Props 是父组件的数据，子组件不能改别人的数据
  → 这保证了单向数据流的可预测性
  → 如果子组件需要"可变值"，用自己的 state
```

### 3.3 默认值与 children

```jsx
// 默认值：用 JS 解构默认值语法
function Button({ text = '点击', variant = 'primary', size = 'md' }) {
  return <button className={`btn btn-${variant} btn-${size}`}>{text}</button>
}

// 相当于：
<Button />                              // text='点击', variant='primary', size='md'
<Button text="提交" variant="danger" />  // text='提交', variant='danger', size='md'


// children：一个特殊的 prop，是标签之间的内容
function Card({ title, children }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <div className="card-body">{children}</div>
    </div>
  )
}

<Card title="用户信息">
  <p>这里的所有内容</p>     {/* ← 这些就是 children */}
  <p>都会传给 Card 组件</p>
</Card>

// children 可以是任何东西：文本、JSX、组件、甚至函数
// 和 Vue 的 <slot> 概念一样
```

### 3.4 Props 展开传递

```jsx
// 当 props 很多时，可以展开传递
const userProps = { name: '张三', age: 25, isOnline: true }

// 展开传递：等价于 name="张三" age={25} isOnline={true}
<UserCard {...userProps} />

// 常见场景：透传 props 给内部元素
function Input({ label, ...inputProps }) {
  return (
    <label>
      {label}
      <input {...inputProps} />   {/* 把剩余 props 全部传给 input */}
    </label>
  )
}

<Input label="用户名" type="text" placeholder="请输入" maxLength={20} />
// label 被 Input 自己用了
// type, placeholder, maxLength 都透传给了 <input>
```

---

## 4. State：组件的记忆

### 4.1 为什么需要 State

```
普通变量不能驱动 UI 更新：

function Counter() {
  let count = 0          // 普通变量

  const handleClick = () => {
    count++              // 值确实变了
    console.log(count)   // 控制台能看到 1, 2, 3...
  }

  return <p>{count}</p>  // ❌ 但 UI 永远显示 0！
}

为什么？
  → 组件函数每次渲染都重新执行
  → let count = 0 每次都重置为 0
  → 即使你改了 count，React 也不知道需要重新渲染

React 需要两样东西：
  1. 在渲染之间保持值（不被重置）
  2. 值变化时触发重新渲染

这就是 useState 的作用。
```

### 4.2 useState 基本用法

```jsx
import { useState } from 'react'

function Counter() {
  //    当前值    更新函数     初始值
  const [count, setCount] = useState(0)
  //     ↑        ↑
  //     读        写

  return (
    <div>
      <p>计数: {count}</p>
      <button onClick={() => setCount(count + 1)}>+1</button>
      <button onClick={() => setCount(0)}>重置</button>
    </div>
  )
}

// 解析：
// useState(0) 告诉 React："帮我记住一个值，初始是 0"
// count：当前的值（只读，你不能 count = 5）
// setCount：更新函数（调用它 → React 记住新值 → 触发重新渲染）
```

### 4.3 useState 的工作原理

```
理解 useState 的关键是"快照"：

  第 1 次渲染：useState(0) → count = 0
    → 用户点击 +1
    → setCount(1) 被调用
    → React 安排重新渲染

  第 2 次渲染：useState(0) → count = 1（React 记住了）
    → 这次渲染中所有的 count 都是 1
    → 这是一个全新的函数调用，count 是新的局部变量

  第 3 次渲染：useState(0) → count = 2

⭐ 每次渲染都是一张"快照"：
  → count 是这张快照里的一个常量
  → 本次渲染中 count 不会变
  → 只有下次渲染时才能"看到"新值
```

### 4.4 setState 是"异步"的

```jsx
function Counter() {
  const [count, setCount] = useState(0)

  const handleClick = () => {
    setCount(count + 1)
    console.log(count)     // ⚠️ 还是 0，不是 1！

    // 为什么？
    // 因为 setCount 不是"立即改变 count"
    // 它是告诉 React："下次渲染时，用新值"
    // 在当前这次渲染中，count 是个常量，值不会变

    setCount(count + 1)
    setCount(count + 1)
    // ⚠️ 连续调用 3 次，count 最终只变成 1，不是 3！
    // 因为这 3 次调用中，count 都是 0
    // 所以等于 setCount(0+1) 三次 = setCount(1) 三次
  }

  return <button onClick={handleClick}>{count}</button>
}
```

### 4.5 函数式更新（解决上面的问题）

```jsx
function Counter() {
  const [count, setCount] = useState(0)

  const handleClick = () => {
    // ✅ 函数式更新：基于"最新值"计算，而不是快照值
    setCount(prev => prev + 1)  // 0 → 1
    setCount(prev => prev + 1)  // 1 → 2
    setCount(prev => prev + 1)  // 2 → 3

    // prev 是 React 内部维护的最新值，不是闭包里的快照
    // 每次调用都基于上一次的结果
  }

  return <button onClick={handleClick}>{count}</button>
}

// ⭐ 经验法则：
//   简单赋值 → setCount(5)                    // 直接设值
//   基于旧值 → setCount(prev => prev + 1)     // 函数式更新
//   连续调用多次 → 必须用函数式更新
```

### 4.6 多个 State

```jsx
function TodoApp() {
  const [todos, setTodos] = useState([])      // 待办列表
  const [input, setInput] = useState('')       // 输入框内容
  const [filter, setFilter] = useState('all')  // 筛选条件

  // ⭐ 每个 useState 管理一个独立的状态
  // 相关的状态可以合并成一个对象（用 useReducer 更好，阶段 3 会讲）
  // 不相关的状态分开存（方便独立更新）

  return (/* ... */)
}
```

---

## 5. 事件处理

### 5.1 基本语法

```jsx
function ButtonDemo() {
  // 方式 1：内联函数（简单逻辑）
  return <button onClick={() => alert('点击了')}>点击</button>

  // 方式 2：独立函数（复杂逻辑，推荐）
  const handleClick = () => {
    console.log('执行复杂逻辑...')
  }
  return <button onClick={handleClick}>点击</button>

  // ⚠️ 常见错误：
  // ❌ onClick={handleClick()}     ← 立即执行！组件一渲染就触发
  // ✅ onClick={handleClick}       ← 传函数引用，点击时才执行
  // ✅ onClick={() => handleClick()} ← 如果需要传参，包一层箭头函数
}
```

### 5.2 事件对象

```jsx
function InputDemo() {
  const handleChange = (e) => {
    // e 是 React 的合成事件（SyntheticEvent），不是原生 DOM 事件
    // 但用法基本一样
    console.log(e.target.value)   // 输入框当前值
    console.log(e.target.name)    // 输入框的 name 属性
  }

  const handleSubmit = (e) => {
    e.preventDefault()   // ⭐ 阻止表单默认提交行为（刷新页面）
    // 处理提交逻辑...
  }

  return (
    <form onSubmit={handleSubmit}>
      <input name="username" onChange={handleChange} />
      <button type="submit">提交</button>
    </form>
  )
}
```

### 5.3 事件传参

```jsx
function TodoList({ todos, onDelete }) {
  return (
    <ul>
      {todos.map(todo => (
        <li key={todo.id}>
          {todo.text}

          {/* ✅ 方式 1：箭头函数包裹（最常用） */}
          <button onClick={() => onDelete(todo.id)}>删除</button>

          {/* ❌ 错误：直接调用，渲染时就执行了 */}
          <button onClick={onDelete(todo.id)}>删除</button>
        </li>
      ))}
    </ul>
  )
}

// 为什么需要箭头函数包裹？
// onClick 需要一个"函数"，点击时才调用
// onDelete(todo.id) 是"函数调用的结果"，渲染时就执行了
// () => onDelete(todo.id) 是"一个函数"，点击时才执行里面的代码
```

### 5.4 React 事件 vs DOM 事件

```
React 的事件系统（合成事件）和原生 DOM 事件的区别：

  命名：    onClick（驼峰）    vs    onclick（全小写）
  传值：    onClick={fn}      vs    onclick="fn()"
  阻止默认：e.preventDefault()  vs    return false 也行
  事件委托：React 统一委托到 root    vs    你自己绑在每个元素上

  实际上 React 在底层做了兼容处理，你不用关心浏览器差异
  合成事件的 API 和原生事件基本一致，99% 情况下当原生事件用就行
```

---

## 6. 条件渲染

### 6.1 三种方式

```jsx
function StatusBadge({ status }) {

  // 方式 1：三元表达式 ? :（二选一）
  return <span>{status === 'online' ? '🟢 在线' : '⚫ 离线'}</span>

  // 方式 2：&& 短路（显示或不显示）
  return <span>{status === 'online' && '🟢 在线'}</span>
  // 如果 status 不是 online，什么都不渲染

  // 方式 3：提前 return（整块逻辑不同）
  if (status === 'loading') return <Spinner />
  if (status === 'error') return <Error />
  return <Content />
}
```

### 6.2 选择指南

```
用哪种？看场景：

  二选一（A 或 B）   → 三元 ? :
    <span>{isAdmin ? '管理员' : '用户'}</span>

  显示或隐藏        → &&
    {hasError && <ErrorMessage />}
    ⚠️ 陷阱：{count && <p>{count}</p>}
       当 count=0 时，0 是 falsy，但 React 会渲染数字 0 到页面上！
       ✅ 改成：{count > 0 && <p>{count}</p>}

  多分支            → 提前 return 或变量
    let content
    if (status === 'loading') content = <Spinner />
    else if (status === 'error') content = <Error />
    else content = <Data />
    return <div>{content}</div>
```

### 6.3 条件渲染 class / style

```jsx
function Button({ variant, disabled }) {
  // className 拼接
  return (
    <button
      className={`btn ${variant === 'primary' ? 'btn-primary' : 'btn-default'} ${disabled ? 'btn-disabled' : ''}`}
      disabled={disabled}
    >
      提交
    </button>
  )

  // ⭐ 实际项目中用 clsx/classnames 库更清晰：
  // className={clsx('btn', { 'btn-primary': variant === 'primary', 'btn-disabled': disabled })}
}
```

---

## 7. 列表渲染与 key

### 7.1 基本列表渲染

```jsx
function FruitList() {
  const fruits = ['苹果', '香蕉', '橘子']

  return (
    <ul>
      {fruits.map((fruit, index) => (
        <li key={index}>{fruit}</li>
      ))}
    </ul>
  )
  // map 返回一个新数组，每个元素是一段 JSX
  // React 把这个 JSX 数组渲染成多个 <li>
}
```

### 7.2 对象数组渲染

```jsx
function UserList() {
  const users = [
    { id: 1, name: '张三', role: 'admin' },
    { id: 2, name: '李四', role: 'user' },
    { id: 3, name: '王五', role: 'user' },
  ]

  return (
    <ul>
      {users.map(user => (
        <li key={user.id}>                    {/* ⭐ 用 id 做 key */}
          {user.name}（{user.role}）
        </li>
      ))}
    </ul>
  )
}
```

### 7.3 key 的作用和规则 ⭐

```
key 帮 React 的 diff 算法识别列表中的元素：

  旧列表：[A(key=1), B(key=2), C(key=3)]
  新列表：[A(key=1), C(key=3), D(key=4)]

  有 key 时：
    React 知道：A 不变、B 被删了、C 移动了、D 是新增的
    → 精确操作

  没 key / 用 index 做 key 时：
    React 按位置对比：第 1 个 vs 第 1 个、第 2 个 vs 第 2 个...
    → 可能导致错误的复用和 bug

⭐ key 的规则：
  ✅ 用数据的唯一 ID（user.id, todo.id, item.uuid）
  ⚠️ 用 index 做 key：只在列表永远不排序、不增删中间项时才安全
  ❌ 用 Math.random() 做 key：每次渲染都是新 key → 每次都销毁重建 → 性能灾难
  ❌ key 不传：React 会警告，并默认用 index（有 bug 风险）
```

### 7.4 用 index 做 key 的 bug 示例

```
场景：一个可以删除的列表

  初始：[苹果(key=0), 香蕉(key=1), 橘子(key=2)]
  删除"苹果"后：[香蕉(key=0), 橘子(key=1)]

  React 看到的：
    key=0 从"苹果"变成了"香蕉" → 更新 key=0 的内容
    key=1 从"香蕉"变成了"橘子" → 更新 key=1 的内容
    key=2 没了 → 删除

  实际应该是：删除 key=0，其他不动

  如果列表项有输入框或状态，这个 bug 会导致输入框内容串行！

  ✅ 用唯一 ID（如 item.id）做 key，就不会有这个问题
```

---

## 8. 不可变更新

### 8.1 为什么 State 必须不可变

```
React 用 Object.is() 判断 state 是否变化：

  const a = [1, 2, 3]
  const b = a
  a.push(4)
  Object.is(a, b)  // true！因为 a 和 b 是同一个引用

  → 你改了数组的内容，但引用没变
  → React 认为 state 没变
  → 不触发重新渲染
  → UI 不更新

所以必须创建新的引用：
  const a = [1, 2, 3]
  const c = [...a, 4]   // 新数组
  Object.is(a, c)       // false → React 知道变了 → 重新渲染
```

### 8.2 数组的不可变操作

```jsx
// ✅ 添加
setTodos([...todos, newTodo])          // 末尾追加
setTodos([newTodo, ...todos])          // 开头追加

// ✅ 删除
setTodos(todos.filter(t => t.id !== id))

// ✅ 修改某一项
setTodos(todos.map(t =>
  t.id === id ? { ...t, done: true } : t
))

// ✅ 排序（先复制再排序）
setTodos([...todos].sort((a, b) => a.text.localeCompare(b.text)))

// ❌ 直接修改
todos.push(newTodo)     // ❌
todos.splice(index, 1)  // ❌
todos[0].done = true    // ❌
todos.sort()            // ❌ sort 会修改原数组
```

### 8.3 对象的不可变操作

```jsx
const [user, setUser] = useState({ name: '张三', age: 25, address: { city: '北京' } })

// ✅ 修改顶层属性
setUser({ ...user, name: '李四' })
//       ↑ 展开旧对象的所有属性，然后覆盖 name

// ✅ 修改嵌套属性
setUser({
  ...user,
  address: { ...user.address, city: '上海' }
  //         ↑ 嵌套对象也要展开再覆盖
})

// ❌ 直接修改
user.name = '李四'              // ❌
user.address.city = '上海'      // ❌

// ⚠️ 嵌套很深时展开很麻烦 → 可以用 Immer 库（后续会提到）
```

### 8.4 Vue 对比

```
React 的不可变更新 vs Vue 的可变更新：

  React：
    setUser({ ...user, name: '李四' })
    → 你必须显式创建新对象
    → 更啰嗦，但数据变化可追踪、可预测

  Vue：
    user.name = '李四'
    → Proxy 自动拦截 set 操作
    → 更简洁，但变更来源更隐式

  两者都能正确更新 UI，只是思维方式不同
  React 的方式更"函数式"（无副作用）
  Vue 的方式更"面向对象"（直接修改状态）
```

---

## 9. 组件拆分与单向数据流

### 9.1 何时拆分组件

```
拆分的信号：
  ✅ 组件超过 100-150 行
  ✅ 有明显的独立功能块（输入区、列表区、筛选区）
  ✅ 有在多处复用的 UI 片段
  ✅ 有独立的状态逻辑

不需要拆的情况：
  ❌ 为了"拆"而拆（增加了 props 传递成本，没有简化逻辑）
  ❌ 组件只在一个地方用，且逻辑简单
```

### 9.2 完整示例：拆分 TodoApp

```jsx
// ────── 子组件：输入区 ──────
function TodoInput({ onAdd }) {
  const [text, setText] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!text.trim()) return
    onAdd(text)          // 通过回调通知父组件
    setText('')
  }

  return (
    <form onSubmit={handleSubmit}>
      <input value={text} onChange={e => setText(e.target.value)} placeholder="输入待办..." />
      <button type="submit">添加</button>
    </form>
  )
}

// ────── 子组件：单条 Todo ──────
function TodoItem({ todo, onToggle, onDelete }) {
  return (
    <li style={{ textDecoration: todo.done ? 'line-through' : 'none' }}>
      <span onClick={() => onToggle(todo.id)}>{todo.text}</span>
      <button onClick={() => onDelete(todo.id)}>删除</button>
    </li>
  )
}

// ────── 子组件：筛选栏 ──────
function TodoFilter({ filter, onFilterChange }) {
  return (
    <div>
      {['all', 'active', 'done'].map(f => (
        <button
          key={f}
          onClick={() => onFilterChange(f)}
          style={{ fontWeight: f === filter ? 'bold' : 'normal' }}
        >
          {f === 'all' ? '全部' : f === 'active' ? '未完成' : '已完成'}
        </button>
      ))}
    </div>
  )
}

// ────── 父组件：管理所有状态 ──────
function TodoApp() {
  const [todos, setTodos] = useState([])
  const [filter, setFilter] = useState('all')

  const handleAdd = (text) => {
    setTodos(prev => [...prev, { id: Date.now(), text, done: false }])
  }
  const handleToggle = (id) => {
    setTodos(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t))
  }
  const handleDelete = (id) => {
    setTodos(prev => prev.filter(t => t.id !== id))
  }

  const filteredTodos = todos.filter(t =>
    filter === 'all' ? true : filter === 'done' ? t.done : !t.done
  )

  return (
    <div>
      <h1>待办事项（{todos.length}）</h1>
      <TodoInput onAdd={handleAdd} />
      <TodoFilter filter={filter} onFilterChange={setFilter} />
      <ul>
        {filteredTodos.map(todo => (
          <TodoItem
            key={todo.id}
            todo={todo}
            onToggle={handleToggle}
            onDelete={handleDelete}
          />
        ))}
      </ul>
      {filteredTodos.length === 0 && <p>暂无待办</p>}
    </div>
  )
}
```

### 9.3 数据流图解

```
                      TodoApp
          (state: todos, filter)
         ┌───────────┼───────────┐
         ↓           ↓           ↓
    TodoInput    TodoFilter   TodoItem × N

    数据下行（props）：
      TodoApp → TodoFilter：传 filter 值
      TodoApp → TodoItem：  传 todo 数据

    事件上行（回调）：
      TodoInput → TodoApp：  onAdd(text)
      TodoFilter → TodoApp：  onFilterChange(filter)
      TodoItem → TodoApp：    onToggle(id) / onDelete(id)

    ⭐ 所有 state 都在 TodoApp 里
    ⭐ 子组件只负责 UI 展示 + 调用回调
    ⭐ 这就是"状态提升"（Lifting State Up）
```

---

## 10. State 设计原则

### 10.1 最小化 State

```
原则：能从现有 state 算出来的值，就不要新建 state

  ❌ 冗余 state：
  const [todos, setTodos] = useState([...])
  const [totalCount, setTotalCount] = useState(0)     // 多余！= todos.length
  const [doneCount, setDoneCount] = useState(0)        // 多余！= todos.filter(t => t.done).length
  const [filteredTodos, setFilteredTodos] = useState([]) // 多余！= 根据 filter 和 todos 算出

  ✅ 只存不可推导的最小状态：
  const [todos, setTodos] = useState([...])
  const [filter, setFilter] = useState('all')

  // 派生值直接在渲染时计算
  const totalCount = todos.length
  const doneCount = todos.filter(t => t.done).length
  const filteredTodos = todos.filter(t => ...)
```

### 10.2 惰性初始值

```jsx
// 当初始值计算很昂贵时，传函数给 useState

// ❌ 每次渲染都执行 expensiveComputation()
const [data, setData] = useState(expensiveComputation())

// ✅ 只在首次渲染时执行
const [data, setData] = useState(() => expensiveComputation())

// 常见场景：从 localStorage 读取初始值
const [theme, setTheme] = useState(() => {
  return localStorage.getItem('theme') || 'light'
})
```

### 10.3 State vs 普通变量 vs Ref

```
三者的选择依据：

  值变化时需要重新渲染吗？
    是 → useState（UI 上直接展示的数据）
    否 →
      值需要在渲染之间保持吗？
        是 → useRef（定时器 ID、DOM 引用、上次的值）
        否 → 普通变量（中间计算结果、临时变量）

  示例：
    useState: 用户输入、列表数据、loading 状态、modal 开关
    useRef:   定时器 ID、表单 DOM 引用、前一次 props 值
    普通变量: filteredList（从 state 派生）、格式化后的字符串
```

---

## 11. 面试常问

### Q1: JSX 是什么？为什么用 JSX 而不是模板？

**答**：
- JSX 是 `React.createElement()` 的语法糖，编译后就是 JS 函数调用，返回虚拟 DOM 对象
- 选择 JSX 而非模板的原因：JSX 就是 JS，拥有 JS 的全部编程能力（条件、循环、变量、函数...）；不需要学习模板专用语法（v-if、v-for 等）；IDE 支持更好（类型检查、重构、自动补全）
- 缺点：对不熟悉 JS 的人入门更难，且需要构建工具编译

### Q2: 为什么 State 要用不可变更新？

**答**：
- React 用 `Object.is()` 比较新旧 state 的引用来决定是否重新渲染
- 直接修改（`todos.push()`）不会改变引用 → React 认为没变化 → 不重新渲染 → UI 不更新
- 创建新对象（`[...todos, newTodo]`）会产生新引用 → React 检测到变化 → 触发重新渲染
- 附带好处：不可变数据更容易追踪变化、实现时间旅行调试、支持 React.memo 的浅比较优化

### Q3: key 的作用是什么？为什么不能用 index？

**答**：
- key 帮助 React 在 diff 时识别列表中哪些元素增加了、删除了、移动了
- 不用 index 是因为：当列表发生增删或排序时，index 和元素的对应关系会变
  - 比如删除第一项后，原来 index=1 的变成了 index=0，React 会认为是"第一项内容变了"而不是"第一项被删了"
  - 如果列表项有内部状态（如输入框），会导致状态错乱
- 用数据的唯一 ID（如数据库 id）做 key，就不会有这个问题

### Q4: 受控组件是什么？

**答**：
- 表单元素（input/select/textarea）的值由 React state 管理，通过 `value` + `onChange` 实现
- 每次用户输入 → `onChange` 触发 → `setState` 更新 → React 重新渲染 → input 显示新值
- 优点：React 完全控制表单值，方便做验证、格式化、联动
- 对比"非受控组件"：用 `defaultValue` + `ref` 直接从 DOM 读取值，React 不参与管理
- → 阶段 5 会详细对比受控 vs 非受控的使用场景和决策方法

### Q5: Props 和 State 的区别？

**答**：

| | Props | State |
|--|-------|-------|
| 来源 | 父组件传入 | 组件自己管理 |
| 可变性 | 只读（不能修改） | 可通过 setState 更新 |
| 用途 | 配置组件行为 | 存储可变数据 |
| 变化触发渲染 | 间接（父组件重渲染） | 直接（setState 触发） |

一句话：Props 是"别人告诉你的"，State 是"你自己记住的"。

---

## 12. 练习

```
基础：
  1. 从零写一个 Counter 组件（+1, -1, 重置），用 console.log 观察每次渲染
  2. 写一个 UserCard 组件，接收 name, avatar, bio 三个 props，用默认值处理缺失情况
  3. 写一个列表组件，用 map 渲染，输入框可以添加新项 → 确认你理解了受控组件

综合：
  4. 从零写一个完整的 TodoApp（增删改 + 标记完成 + 筛选），不看上面的代码
     → 要求：拆成至少 3 个组件（TodoInput + TodoItem + TodoFilter）
     → 要求：state 只放在父组件，子组件用 props + 回调
  5. 在 TodoApp 中故意直接修改 state（todos.push），观察 UI 不更新
     → 然后改成不可变更新，看 UI 恢复正常

进阶：
  6. 给 TodoApp 加上 localStorage 持久化：
     → 初始化时从 localStorage 读取（用惰性初始值）
     → 每次 todos 变化时写入 localStorage（这个需要 useEffect，阶段 3 会学）
  7. 写一个通用的 Select 组件，接收 options 数组和 onChange 回调
     → 思考：这个组件应该是受控的还是非受控的？
```

---

## 📖 推荐学习路径

1. 阅读 [react.dev - Your First Component](https://react.dev/learn/your-first-component) 和 [Describing the UI](https://react.dev/learn/describing-the-ui) 系列
2. 亲手写完练习 4（完整 TodoApp），这是检验本阶段的核心标准
3. 确保理解：useState 的"快照"模型、不可变更新的原因、key 的作用

> ⬅️ [上一阶段：核心心智模型](./01-mental-model.md) | ➡️ [下一阶段：Hooks 深度理解](./03-hooks-deep-dive.md)
