# React 系统学习路线（复习向）

> **前提**：你已经学过一遍 React，但实际工作中发现很多忘了。本路线帮你系统复习，重建肌肉记忆，侧重「为什么」而不只是「怎么用」。

---

## 学习路线概览

```
阶段 1：核心心智模型 + 渲染机制（半天）
  → UI = f(state) + 完整渲染流程 → 这是贯穿全文的主线

阶段 2：第一个完整组件（1-2 天）
  → JSX + Props + State + 事件 + 条件/列表渲染
  → 在一个完整组件中自然覆盖所有基础

阶段 3：Hooks 深度理解（2-3 天）⭐ 最核心
  → useState → useEffect → useRef → useContext → useReducer
  → 穿插组件生命周期，理解每个 Hook 在什么"时机"执行

阶段 4：TypeScript + React（1 天）
  → 从这里开始所有代码都用 TS（前置，不是附属品）

阶段 5：组件设计 & 复用模式（1-2 天）
  → 受控/非受控 + 组合模式 + 自定义 Hook + 关注点分离

阶段 6：路由 + 数据层（1-2 天）
  → React Router + TanStack Query

阶段 7：状态管理 + 性能优化（2 天）
  → Context → Zustand → React.memo → DevTools
  → 统一在"渲染优化"主线下

阶段 8：现代 React 生态 + 实战（3-5 天）
  → React 19 新特性 + Next.js 概念 + 3 个递进项目
```

**总预计时间**：12-16 天（每天 2-3 小时）

---

## 🔴 贯穿全文的主线：渲染机制

```
这是 React 最重要的心智模型，所有阶段的知识都围绕它展开：

  State 变化 → 触发重新渲染 → 生成新的虚拟 DOM → Diff 对比 → 最小化更新真实 DOM

  阶段 1 建立这个认知
  阶段 2 亲手触发这个流程
  阶段 3 学会用 Hooks 控制这个流程的各个环节
  阶段 5 学会如何优雅地组织这个流程
  阶段 7 学会优化这个流程的性能
```

---

## 阶段 1：核心心智模型 + 渲染机制

### React 的本质

React 的本质就一句话：**UI = f(state)**

```
传统方式（jQuery / 原生 JS）：
  1. 手动找到 DOM 节点
  2. 手动修改 DOM
  3. 状态散落各处，难以追踪
  → 命令式："第 1 步做这个，第 2 步做那个"

React 方式：
  1. 你只管声明 "状态 X 对应 UI Y"
  2. 状态变了 → React 自动算出新 UI → 自动更新 DOM
  3. 你永远不直接操作 DOM
  → 声明式："我要这个结果"
```

### 渲染流程全景图

```
                    ┌─────────────────────────────────────────┐
                    │          React 渲染流程                   │
                    │                                          │
  setState() ──→  触发渲染  ──→  调用组件函数  ──→  返回新 JSX    │
                    │              ↓                            │
                    │         生成虚拟 DOM（JS 对象）              │
                    │              ↓                            │
                    │      与上一次虚拟 DOM 做 Diff               │
                    │              ↓                            │
                    │      计算出最小变更集                       │
                    │              ↓                            │
                    │      更新真实 DOM（Commit 阶段）            │
                    │              ↓                            │
                    │      浏览器绘制 → 用户看到变化               │
                    └─────────────────────────────────────────┘

⭐ 关键认知：
  - "重新渲染" = 重新调用组件函数 ≠ 重新创建 DOM
  - 虚拟 DOM 不是为了"快"，是为了让声明式编程变得实用
  - React 的 Diff 算法假设：不同类型的元素产生不同的树 + key 标识同级元素
```

### 和 Vue 的对比（如果你有 Vue 经验）

```
                      React                    Vue
数据驱动             state → 重新调用整个函数    响应式 proxy 精确追踪
模板/渲染            JSX（就是 JS）            template（类 HTML）
更新粒度             组件级重新渲染 + diff       属性级精确更新
状态管理             不可变（新对象替换旧对象）    可变（直接修改触发响应式）
心智模型             函数式 → 每次渲染是快照       响应式 → 数据变了 UI 自动变

核心区别：
  Vue：你改 this.count++，Vue 的 proxy 自动知道，精确更新用到 count 的地方
  React：你调 setCount(count+1)，React 重新执行整个组件函数，diff 后更新 DOM
  
  → React 更"笨"但更可预测，Vue 更"聪明"但更隐式
```

### 练习

```
1. 用自己的话解释：为什么 React 不直接操作 DOM？
2. 画出 setState → 屏幕更新的完整流程
3. 解释 "虚拟 DOM" 和 "真实 DOM" 的区别
```

---

## 阶段 2：第一个完整组件

> 不再拆成 JSX / Props / State / 事件 四个独立阶段。
> 通过构建一个逐步增强的组件，在实践中自然覆盖所有基础。

### 2.1 从零开始：静态组件

```jsx
// 组件 = 返回 JSX 的函数，仅此而已
// JSX = React.createElement() 的语法糖
function TodoApp() {
  return (
    <div className="app">        {/* ← className，不是 class */}
      <h1>待办事项</h1>            {/* ← {} 里写 JS 表达式 */}
      <input placeholder="输入..." />
      <ul>
        <li>学习 React</li>
        <li>写代码</li>
      </ul>
    </div>
  )
}
// ✅ 组件名大写（React 靠大小写区分 HTML 元素和自定义组件）
// ✅ 必须有唯一根元素（或用 <></> Fragment）
// ✅ style 要写对象：style={{ color: 'red', fontSize: 16 }}
```

### 2.2 加入 State：让组件动起来

```jsx
import { useState } from 'react'

function TodoApp() {
  // ⭐ useState：组件的"记忆"
  const [todos, setTodos] = useState([        // 初始值
    { id: 1, text: '学习 React', done: false },
  ])
  const [input, setInput] = useState('')

  return (
    <div className="app">
      <h1>待办事项（{todos.length}）</h1>
      <input
        value={input}                         // ← 受控组件：React 管理值
        onChange={e => setInput(e.target.value)} // ← 事件处理
      />
      <ul>
        {todos.map(todo => (                  // ← 列表渲染
          <li key={todo.id}>{todo.text}</li>   // ← key: 帮 React 追踪元素
        ))}
      </ul>
      {todos.length === 0 && <p>暂无待办</p>}  {/* ← 条件渲染 */}
    </div>
  )
}
```

### 2.3 加入交互：事件处理 + State 不可变更新

```jsx
function TodoApp() {
  const [todos, setTodos] = useState([])
  const [input, setInput] = useState('')

  // 添加
  const handleAdd = () => {
    if (!input.trim()) return
    // ⭐ 不可变更新：创建新数组，不修改原数组
    setTodos([...todos, { id: Date.now(), text: input, done: false }])
    //       ↑ 展开旧数组 + 追加新元素 = 新数组
    setInput('')
  }

  // 切换完成
  const handleToggle = (id) => {
    setTodos(todos.map(t =>          // map 返回新数组
      t.id === id ? { ...t, done: !t.done } : t  // 展开 + 覆盖 = 新对象
    ))
  }

  // 删除
  const handleDelete = (id) => {
    setTodos(todos.filter(t => t.id !== id))  // filter 返回新数组
  }

  // 提交
  const handleSubmit = (e) => {
    e.preventDefault()     // ⭐ 阻止表单默认提交行为
    handleAdd()
  }

  return (
    <form onSubmit={handleSubmit}>
      <input value={input} onChange={e => setInput(e.target.value)} />
      <button type="submit">添加</button>
      <ul>
        {todos.map(todo => (
          <li key={todo.id} style={{ textDecoration: todo.done ? 'line-through' : 'none' }}>
            <span onClick={() => handleToggle(todo.id)}>{todo.text}</span>
            <button onClick={() => handleDelete(todo.id)}>删除</button>
          </li>
        ))}
      </ul>
    </form>
  )
}
```

### 2.4 拆分组件：Props 传递

```jsx
// 子组件：只负责展示一条 todo
// Props = 函数参数，只读
function TodoItem({ todo, onToggle, onDelete }) {
  return (
    <li style={{ textDecoration: todo.done ? 'line-through' : 'none' }}>
      <span onClick={() => onToggle(todo.id)}>{todo.text}</span>
      <button onClick={() => onDelete(todo.id)}>删除</button>
    </li>
  )
}

// 父组件：管理状态，通过 props 传给子组件
function TodoApp() {
  const [todos, setTodos] = useState([])
  // ...（同上）

  return (
    <ul>
      {todos.map(todo => (
        <TodoItem
          key={todo.id}
          todo={todo}
          onToggle={handleToggle}    // ← 传回调函数，子组件通过它"向上通信"
          onDelete={handleDelete}
        />
      ))}
    </ul>
  )
}

// ⭐ 单向数据流：
//   数据通过 props 从 父 → 子
//   事件通过 回调函数 从 子 → 父
//   这让数据流向可预测、可追踪
```

### ⚠️ State 关键规则总结

```
1. 不可变性（Immutability）：
   ❌ todos.push(newItem)              // 直接修改原数组
   ✅ setTodos([...todos, newItem])     // 创建新数组
   
   为什么？React 用 Object.is() 比较引用决定是否重新渲染
   直接修改 → 引用不变 → React 认为没变 → 不更新 UI

2. 函数式更新（避免闭包陷阱）：
   ❌ setCount(count + 1); setCount(count + 1)  // count 还是旧值，最终只 +1
   ✅ setCount(prev => prev + 1); setCount(prev => prev + 1)  // 基于最新值，+2

3. State 提升：
   两个兄弟组件需要共享状态？→ 提升到共同父组件 → 通过 props 传下去

4. key 的作用：
   ❌ 用 index 做 key（增删排序时 React 会混淆元素）
   ✅ 用数据的唯一 ID（todo.id）

5. 惰性初始值（初始值计算很昂贵时）：
   ❌ useState(expensiveComputation())        // 每次渲染都执行，浪费
   ✅ useState(() => expensiveComputation())  // 只在首次渲染时执行

6. 最小化 State：
   能从现有 state 算出来的，就不要新建 state
   ❌ const [count, setCount] = useState(0)   // 多余！
   ✅ 直接用 todos.length，不要另存一个 count
```

### 练习

```
1. 从零写一个 TodoApp（增删改 + 标记完成），不看上面的代码
2. 加入筛选功能（全部/已完成/未完成），用条件渲染 + 数组 filter
3. 拆成 3 个组件（TodoInput + TodoItem + TodoFilter），确认你理解 props 传递
4. 故意直接修改 state（todos.push），观察 UI 不更新，理解不可变性
```

---

## 阶段 3：Hooks 深度理解 ⭐

### 组件生命周期全景（理解 Hooks 的前提）

```
虽然函数组件没有 class 的 lifecycle 方法，但依然有生命周期概念：

  挂载（Mount）:  组件第一次出现在页面上
    ↓
  渲染（Render）:  React 调用组件函数，返回 JSX
    ↓
  提交（Commit）:  React 把变更应用到真实 DOM
    ↓
  Effect 执行：   useEffect 的回调在 DOM 更新后异步执行
    ↓
  更新（Update）:  state/props 变化 → 重新 渲染 → 重新 Commit → 重新 Effect
    ↓
  卸载（Unmount）: 组件从页面移除 → useEffect 清理函数执行

                    ┌────────── 更新循环 ──────────┐
                    ↓                              │
  Mount → Render → Commit → Effect → (state变化) ──┘
                                         ↓
                                      Unmount → Cleanup
```

### 3.1 useEffect（副作用处理）⭐ 最容易出错的 Hook

```jsx
import { useState, useEffect } from 'react'

function UserProfile({ userId }) {
  const [user, setUser] = useState(null)

  useEffect(() => {
    // ⭐ 副作用逻辑（数据请求、订阅、DOM 操作等）
    let cancelled = false

    fetch(`/api/users/${userId}`)
      .then(res => res.json())
      .then(data => {
        if (!cancelled) setUser(data)  // 防止竞态：组件卸载后不 setState
      })

    // ⭐ 清理函数：组件卸载或依赖变化时执行
    return () => { cancelled = true }
  }, [userId])
  //    ↑ 依赖数组：只在 userId 变化时重新执行

  if (!user) return <div>加载中...</div>
  return <div>{user.name}</div>
}
```

### useEffect 依赖数组速查

```
useEffect(() => { ... })           // 无依赖 → 每次渲染后执行（几乎不用）
useEffect(() => { ... }, [])       // 空依赖 → 仅挂载时执行一次（≈ onMounted）
useEffect(() => { ... }, [a, b])   // 有依赖 → a 或 b 变化时执行（≈ watch）

⚠️ 三大陷阱：
  1. 依赖没写全 → 用了 state/props 但没放进依赖 → 拿到过期值（闭包陷阱）
  2. 对象/函数做依赖 → 每次渲染都是新引用 → effect 无限执行
  3. 忘记清理 → 定时器/订阅/WebSocket 泄漏

⭐ useEffect 不是 Vue 的 watch！
  Vue watch：精确监听某个值
  React useEffect：在"渲染后的某个时机"执行副作用
  effect 里要做的事 = 和外部世界同步（API、DOM、定时器...）
  不是 effect 的事 = 根据 state 计算新值（直接在组件函数体里算）
```

### 闭包陷阱最小示例

```jsx
// 这是 useEffect 最常见的 bug，必须理解
function Counter() {
  const [count, setCount] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      console.log(count)  // ⚠️ 永远打印 0！
      // 这个函数“记住”了创建时的 count 值（闭包）
      // effect 只在挂载时执行一次（依赖是 []），count 被锁定在 0
    }, 1000)
    return () => clearInterval(timer)
  }, [])  // ← 空依赖，effect 不会重新执行，闭包里的 count 永远是 0

  return <button onClick={() => setCount(c => c + 1)}>{count}</button>
}

// 修复方式 1：把 count 加入依赖（count 变了就重建定时器）
useEffect(() => {
  const timer = setInterval(() => console.log(count), 1000)
  return () => clearInterval(timer)
}, [count])  // count 变了 → 重建定时器

// 修复方式 2：用 ref 存最新值（不重建定时器）
const countRef = useRef(count)
countRef.current = count  // 每次渲染都更新 ref
useEffect(() => {
  const timer = setInterval(() => console.log(countRef.current), 1000)
  return () => clearInterval(timer)
}, [])  // ref.current 永远是最新值
```

### 3.2 useRef（可变值 + DOM 访问）

```jsx
import { useRef, useEffect } from 'react'

// 用途 1：访问 DOM 节点
function AutoFocusInput() {
  const inputRef = useRef(null)  // { current: null }

  useEffect(() => {
    inputRef.current.focus()  // 直接操作 DOM
  }, [])

  return <input ref={inputRef} />
}

// 用途 2：保存不触发渲染的可变值
function StopWatch() {
  const [time, setTime] = useState(0)
  const intervalRef = useRef(null)  // 存定时器 ID

  const start = () => {
    intervalRef.current = setInterval(() => setTime(t => t + 1), 1000)
  }
  const stop = () => clearInterval(intervalRef.current)

  return <div>{time}s <button onClick={start}>开始</button><button onClick={stop}>停止</button></div>
}

// ⭐ useState vs useRef：
// state: 值变 → 重新渲染 → UI 更新（用于"显示在屏幕上的数据"）
// ref:   值变 → 不渲染 → UI 不变（用于"幕后数据"：定时器ID、DOM引用、上次的值）
```

### 3.3 useContext（跨层级传数据）

```jsx
import { createContext, useContext, useState } from 'react'

// 1. 创建
const ThemeContext = createContext('light')

// 2. 提供（通常在顶层）
function App() {
  const [theme, setTheme] = useState('dark')
  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <Page />  {/* 中间隔了多少层都没关系 */}
    </ThemeContext.Provider>
  )
}

// 3. 消费（任意后代组件，不用层层传 props）
function DeepChild() {
  const { theme, setTheme } = useContext(ThemeContext)
  return <button onClick={() => setTheme('light')}>{theme}</button>
}

// ⚠️  Context 的局限：
// Provider value 变化 → 所有消费者重新渲染（即使只用了其中一个字段）
// 适合：少量低频变化的全局数据（主题、语言、用户信息）
// 不适合：频繁变化的大量数据 → 用 Zustand 等状态管理库
```

### 3.4 useReducer（复杂状态逻辑）

```jsx
import { useReducer } from 'react'

// 当 state 逻辑复杂（多字段、多操作类型）时用 useReducer
function reducer(state, action) {
  switch (action.type) {
    case 'add':    return { ...state, items: [...state.items, action.payload] }
    case 'remove': return { ...state, items: state.items.filter(i => i.id !== action.payload) }
    case 'toggle': return { ...state, loading: !state.loading }
    default:       throw new Error(`Unknown action: ${action.type}`)
  }
}

function TodoApp() {
  const [state, dispatch] = useReducer(reducer, { items: [], loading: false })
  //                                    ↑ 纯函数     ↑ 初始状态

  return (
    <button onClick={() => dispatch({ type: 'add', payload: { id: 1, text: '学React' } })}>
      添加
    </button>
  )
}

// useState vs useReducer 决策：
// 1-2 个独立状态 → useState
// 多个关联状态 + 复杂更新逻辑 → useReducer
// 和 Vue 对比：useReducer ≈ Vuex/Pinia 的 actions + mutations 的极简版
```

### ⚠️ Hooks 规则（违反会出 bug）

```
1. 只在函数组件的顶层调用 Hook
   ❌ if (condition) { useState(...) }   // 条件中
   ❌ for (...) { useEffect(...) }       // 循环中
   
   为什么？React 靠调用顺序识别每个 Hook
   条件/循环会打乱顺序 → React 把 state 对错号

2. 只在 React 函数组件或自定义 Hook 中调用
   ❌ 普通函数中调用 useState
```

### 练习

```
1. 用 useEffect + fetch 请求一个公开 API（如 jsonplaceholder），展示数据
2. 实现 useEffect 清理：创建一个倒计时组件，切走页面时定时器要清掉
3. 用 useRef 保存"上一次的值"：显示 "count 从 X 变到了 Y"
4. 用 useContext 实现一个简单的主题切换（dark/light）
5. 把阶段 2 的 TodoApp 用 useReducer 重写
```

---

## 阶段 4：TypeScript + React

> 从这里开始，后续所有代码都用 TypeScript。TS 不是"附加"，是现代 React 开发的标配。
> 阶段 2-3 的代码用 JS 写完全没问题，不需要回去改。从现在起新代码全用 TS 写——练习 1 就是把之前的 TodoApp 迁移到 TS，作为桥接。

### 核心类型写法

```tsx
// 4.1 Props 类型
interface TodoItemProps {
  todo: { id: number; text: string; done: boolean }
  onToggle: (id: number) => void     // 回调函数
  onDelete: (id: number) => void
  priority?: 'high' | 'low'          // 可选 + 联合类型
  children?: React.ReactNode          // 可以接收 JSX
}

function TodoItem({ todo, onToggle, onDelete, priority = 'low' }: TodoItemProps) {
  return <li className={priority}>{todo.text}</li>
}

// 4.2 Hooks 泛型
const [user, setUser] = useState<User | null>(null)      // 初始 null 需要显式类型
const [todos, setTodos] = useState<Todo[]>([])            // 空数组需要指定元素类型
const inputRef = useRef<HTMLInputElement>(null)            // DOM 引用类型

// 4.3 事件类型
const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => { ... }
const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => { ... }
const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => { ... }

// 4.4 通用组件（泛型组件）
interface ListProps<T> {
  items: T[]
  renderItem: (item: T) => React.ReactNode
}

function List<T>({ items, renderItem }: ListProps<T>) {
  return <ul>{items.map(renderItem)}</ul>
}
// 使用：<List items={users} renderItem={user => <li>{user.name}</li>} />
```

### 练习

```
1. 为阶段 2 的 TodoApp 加上完整的 TypeScript 类型
2. 写一个泛型的 Select 组件，接受 T[] 类型的 options
```

---

## 阶段 5：组件设计 & 复用模式

### 模式决策树

```
你要解决什么问题？

  "表单元素的值由谁管？"
    → React 管（推荐）→ 受控组件：value + onChange
    → DOM 管           → 非受控组件：defaultValue + ref

  "多个组件有相同的状态逻辑"
    → 提取自定义 Hook → useFetch, useForm, useDebounce...

  "组件内部结构需要灵活替换？"
    → 用 children / 插槽模式（最常用）
    → 用 Render Props（传渲染函数，现在较少用，已被自定义 Hook 取代）

  "组件既有数据逻辑又有 UI？"
    → 用自定义 Hook 提取逻辑（推荐）
    → 或用 容器/展示 分离
```

### 5.1 自定义 Hook：最核心的复用方式 ⭐

```tsx
// 自定义 Hook = 以 use 开头的函数 + 内部调用其他 Hook
// 核心价值：把有状态的逻辑从组件中抽出来，多个组件复用

// 例 1：通用请求 Hook
function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(url)
      .then(r => r.json())
      .then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(e => { if (!cancelled) { setError(e); setLoading(false) } })
    return () => { cancelled = true }
  }, [url])

  return { data, loading, error }
}

// 例 2：防抖 Hook
function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

// 使用：任何组件都能复用
function SearchPage() {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebounce(query, 300)
  const { data, loading } = useFetch<Result[]>(`/api/search?q=${debouncedQuery}`)
  // ...
}
```

### 5.2 组合模式 & children

```tsx
// children = 最自然的"插槽"
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      <div className="card-body">{children}</div>
    </div>
  )
}

// 使用：结构灵活，内容随调用方决定
<Card title="用户信息">
  <Avatar url={user.avatar} />
  <p>{user.bio}</p>
</Card>

// 多插槽：用 props 传 JSX
<Card
  title="仪表盘"
  header={<Breadcrumb />}      // ← "具名插槽"
  footer={<Pagination />}
>
  <DataTable data={data} />     // ← children 默认插槽
</Card>
```

### 练习

```
1. 提取一个 useLocalStorage Hook（读写 localStorage + 状态同步）
2. 用 children 模式写一个 Modal 组件（可以放任意内容）
3. 把之前的 TodoApp 重构：逻辑放 useTodos Hook，UI 放 TodoApp 组件
```

---

## 阶段 6：路由 + 数据层

> 单个组件的设计和复用搞定了，现在学如何把多个组件组织成一个完整的多页面应用，以及如何与后端 API 交互。

### 6.1 React Router v6+

```tsx
import { BrowserRouter, Routes, Route, Link, useParams, useNavigate, Outlet } from 'react-router-dom'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>           {/* 嵌套路由 */}
          <Route index element={<Home />} />             {/* 默认子路由 */}
          <Route path="users" element={<UserList />} />
          <Route path="users/:id" element={<UserDetail />} />  {/* 动态参数 */}
          <Route path="*" element={<NotFound />} />      {/* 404 */}
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

function Layout() {
  return (
    <div>
      <nav><Link to="/">首页</Link> | <Link to="/users">用户</Link></nav>
      <Outlet />  {/* ← 子路由渲染位置，相当于 Vue 的 <router-view> */}
    </div>
  )
}

function UserDetail() {
  const { id } = useParams()         // 获取路由参数（≈ Vue useRoute().params）
  const navigate = useNavigate()      // 编程式导航（≈ Vue useRouter().push）
  return <button onClick={() => navigate('/users')}>返回</button>
}
```

### 6.2 TanStack Query（服务端状态管理）

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

function UserList() {
  // 声明式数据请求：自动处理 loading / error / 缓存 / 重试
  const { data: users, isLoading, error } = useQuery({
    queryKey: ['users'],                                    // 缓存 key
    queryFn: () => fetch('/api/users').then(r => r.json()), // 请求函数
    staleTime: 5 * 60 * 1000,                               // 5 分钟内用缓存
  })

  // 修改操作：自动刷新相关查询
  const queryClient = useQueryClient()
  const createUser = useMutation({
    mutationFn: (newUser: User) =>
      fetch('/api/users', { method: 'POST', body: JSON.stringify(newUser) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  if (isLoading) return <Spinner />
  if (error) return <Error />
  return <ul>{users.map(u => <li key={u.id}>{u.name}</li>)}</ul>
}

// 为什么用 TanStack Query 而不是 useEffect + fetch？
// 1. 自动缓存和去重（多个组件请求同一 API 只发一次）
// 2. 自动重试和后台刷新
// 3. Loading/Error 状态标准化
// 4. 和 Vue Query 是同一个库，概念完全相通
```

### 练习

```
1. 用 React Router 搭一个 3 页面的 SPA（首页 + 列表 + 详情），含嵌套路由
2. 用 TanStack Query 请求 jsonplaceholder API，实现用户列表 + 点击查看详情
```

---

## 阶段 7：状态管理 + 性能优化

> 合为一个阶段，因为它们紧密相关——状态管理的核心问题就是"如何高效地让该更新的更新，不该更新的不更新"。

### 7.1 状态分层：什么数据放哪里？

```
                         状态分层金字塔

              ┌──────────────────────┐
              │   URL State          │  ← React Router（路由参数、查询字符串）
              │   (路由状态)          │
              ├──────────────────────┤
              │   Server State       │  ← TanStack Query（API 数据缓存）
              │   (服务端数据)        │
              ├──────────────────────┤
              │   Global UI State    │  ← Zustand / Context（主题、用户信息、通知）
              │   (全局 UI 状态)      │
              ├──────────────────────┤
              │   Local UI State     │  ← useState（表单输入、开关、模态框开关）
              │   (组件局部状态)      │
              └──────────────────────┘

  ⭐ 不是所有状态都需要"状态管理库"！
  大部分状态是 local state 或 server state，真正需要全局 UI state 的很少。
```

### 7.2 Zustand（推荐的全局状态方案）

```tsx
import { create } from 'zustand'

interface AppStore {
  theme: 'light' | 'dark'
  sidebarOpen: boolean
  toggleTheme: () => void
  toggleSidebar: () => void
}

const useAppStore = create<AppStore>((set) => ({
  theme: 'light',
  sidebarOpen: true,
  toggleTheme: () => set(s => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),
  toggleSidebar: () => set(s => ({ sidebarOpen: !s.sidebarOpen })),
}))

// 使用：任意组件直接用
function Header() {
  const theme = useAppStore(s => s.theme)          // ⭐ 只订阅 theme
  const toggleTheme = useAppStore(s => s.toggleTheme)
  return <button onClick={toggleTheme}>{theme}</button>
}
// 优势 vs Context：
// ✅ 无 Provider（不用包裹）
// ✅ 自动按需渲染（只有读了 theme 的组件才因 theme 变化而重新渲染）
// ✅ 零 boilerplate
```

### 7.3 性能优化（回到渲染主线）

```
⭐ 首先理解：组件什么时候重新渲染？
  1. 自己的 state 变了
  2. 父组件重新渲染了（即使 props 没变！） ← 最常见的"不必要渲染"来源
  3. 消费的 Context value 变了

优化手段（按优先级，先试 1 再试 2...）：
  1. 状态下移：把频繁变化的 state 放到更小的子组件里，避免大组件重新渲染
  2. React.memo：包裹子组件，props 没变就跳过渲染
  3. useMemo：缓存昂贵计算的结果
  4. useCallback：缓存函数引用（配合 React.memo 用才有意义）
  5. 虚拟列表：大列表（>1000 条）用 react-window / react-virtuoso
```

```tsx
import { memo, useMemo, useCallback } from 'react'

// React.memo：props 没变就不重新渲染
const TodoItem = memo(function TodoItem({ todo, onDelete }: TodoItemProps) {
  return <li>{todo.text} <button onClick={() => onDelete(todo.id)}>删</button></li>
})

function TodoApp() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [filter, setFilter] = useState<'all' | 'done' | 'undone'>('all')

  // useMemo：缓存计算结果
  const filtered = useMemo(
    () => todos.filter(t => filter === 'all' ? true : filter === 'done' ? t.done : !t.done),
    [todos, filter]
  )

  // useCallback：缓存函数引用（让 memo 包裹的子组件不会因为"新函数引用"而重新渲染）
  const handleDelete = useCallback((id: number) => {
    setTodos(prev => prev.filter(t => t.id !== id))
  }, [])

  return <ul>{filtered.map(t => <TodoItem key={t.id} todo={t} onDelete={handleDelete} />)}</ul>
}

// ⚠️ 不要过早优化！
// 只在以下情况用 memo/useMemo/useCallback：
//   - 确实有性能问题（用 DevTools Profiler 确认）
//   - 大列表、昂贵计算、频繁渲染
// 90% 的组件不需要优化，React 本身的 diff 已经够快了
```

### React DevTools 使用

```
1. 安装 React DevTools 浏览器扩展
2. Profiler → 录制一段交互 → 看哪些组件渲染了、耗时多久
3. Components → 检查任何组件的 props / state / hooks 值
4. 设置 → "Highlight updates" → 直观看到哪些组件在重新渲染
   ← 你会惊讶地发现很多组件在不必要地重新渲染
```

### 练习

```
1. 用 Zustand 建一个 store 管理主题 + 侧边栏状态
2. 用 React DevTools Profiler 录制你之前 TodoApp 的操作，找出不必要的渲染
3. 用 React.memo + useCallback 优化 TodoItem（用 Profiler 对比优化前后）
```

---

## 阶段 8：现代 React 生态 + 实战

### 8.1 Suspense & Error Boundary（理解 React 19 的前提）

```tsx
import { Suspense } from 'react'
import { ErrorBoundary } from 'react-error-boundary'  // 推荐用这个库

// Suspense：在异步内容加载时显示 fallback
// 你可以把它理解为"声明式的 loading 状态"
function App() {
  return (
    <ErrorBoundary fallback={<div>出错了</div>}>
      <Suspense fallback={<Spinner />}>
        <UserProfile />  {/* 如果内部有异步操作，自动显示 Spinner */}
      </Suspense>
    </ErrorBoundary>
  )
}

// ErrorBoundary：捕获子组件树的渲染错误，防止整个页面崩溃
// ⚠️ React 里唯一必须用 class 的场景（或用 react-error-boundary 库封装）
// 实际工作中，在路由每个页面入口 + 关键模块外层都应该包一个

// 为什么先讲这个？
// 因为 React 19 的 use() Hook 依赖 Suspense 自动处理 loading
// 不理解 Suspense 就无法理解 use()
```

### 8.2 React 19 新特性（2024-2025）

```tsx
// 1. use() Hook：在组件中直接 await Promise
function UserProfile({ userPromise }) {
  const user = use(userPromise)  // ⭐ 自动 Suspense！不再需要手写 loading 状态
  return <div>{user.name}</div>
}

// 2. useActionState（替代 useReducer + form 场景）
function LoginForm() {
  const [state, formAction, isPending] = useActionState(
    async (prevState, formData) => {
      const result = await login(formData.get('email'), formData.get('password'))
      return result
    },
    null
  )
  return (
    <form action={formAction}>
      <input name="email" />
      <button disabled={isPending}>登录</button>
    </form>
  )
}

// 3. useOptimistic（乐观更新 UI）
function TodoList({ todos }) {
  const [optimisticTodos, addOptimistic] = useOptimistic(
    todos,
    (state, newTodo) => [...state, { ...newTodo, sending: true }]
  )
  // 用户点击"添加"后 UI 立即更新，不等 API 返回
}

// 4. ref 可以直接作为 prop 传递（不再需要 forwardRef）
function MyInput({ ref, ...props }) {
  return <input ref={ref} {...props} />
}
```

### 8.3 Server Components 概念（了解即可）

```
传统 React（CSR）：
  浏览器下载 JS → 执行 JS → 渲染 UI → 请求数据 → 再渲染
  问题：首屏白屏、JS bundle 大

Server Components（Next.js App Router）：
  服务器执行组件 → 生成 HTML → 发给浏览器 → 只补充交互用的 JS
  优势：首屏快、bundle 小、可以直接读数据库

  ⭐ 不需要现在深入学，但要知道这是 React 的方向
  如果你要做 SSR / 全栈，→ 学 Next.js
  如果只做纯前端 SPA，→ 用 Vite + React 就够
```

### 8.4 三个递进实战项目

```
项目 1：Todo App（巩固 Stage 1-3）← 2 小时  
  - useState 管理列表 + 筛选
  - 组件拆分 + Props 传递
  - TypeScript 全程
  - 目标：确认 state 不可变更新 + 渲染机制已理解

项目 2：个人仪表盘（衔接 Stage 4-7）← 1-2 天
  - React Router 多页面 + 嵌套路由
  - TanStack Query 请求公开 API（如 GitHub API）
  - Zustand 管理用户设置（主题、布局偏好）
  - React.memo 优化列表渲染
  - 目标：路由 + 数据 + 状态管理 + 性能的完整链路

项目 3：协作看板 Kanban（综合实战）← 3-5 天
  - 拖拽排序（@dnd-kit）
  - TanStack Query 管理服务端数据 + 乐观更新
  - useReducer 管理看板复杂状态
  - 自定义 Hook 提取业务逻辑
  - 目标：接近真实工作场景的复杂度
```

---

## 常见面试题速查

| 问题 | 关键答案 |
|------|---------|
| 虚拟 DOM 是什么？有什么用？ | 内存中的 UI 描述对象树，通过 diff 最小化真实 DOM 操作，让声明式编程可行 |
| 为什么需要 key？ | 帮 React diff 时识别同级元素的增删移，不能用 index（增删排序会出 bug）|
| useEffect vs useLayoutEffect？ | useEffect 异步（不阻塞绘制），useLayoutEffect 同步（阻塞绘制，用于DOM 测量）|
| setState 是同步还是异步？ | React 18+：总是批量异步更新 |
| 为什么不能在条件/循环里用 Hook？ | React 靠调用顺序识别每个 Hook，条件/循环打乱顺序会对错号 |
| React.memo vs useMemo vs useCallback？ | memo: 缓存组件渲染结果；useMemo: 缓存计算值；useCallback: 缓存函数引用 |
| 受控 vs 非受控？ | 受控:React state 管理 value + onChange；非受控:DOM 管理 defaultValue + ref |
| React 和 Vue 核心区别？ | React 组件级重渲染+diff（函数式）；Vue 响应式精确更新（Proxy 追踪依赖）|
| Context 的性能问题？ | value 变化会导致所有消费者渲染，解决：拆分 Context 或用 Zustand |
| Server Components 解决什么？ | 减少客户端 JS bundle，允许组件在服务端执行，改善首屏和 SEO |

---

## 推荐资源

| 资源 | 阶段 | 推荐度 |
|------|------|--------|
| [react.dev](https://react.dev) 官方文档 | 全覆盖 | ⭐⭐⭐⭐⭐（2023 重写后极佳）|
| Fireship - React 速览 (YouTube) | 快速复习 | ⭐⭐⭐⭐⭐ |
| Jack Herrington (YouTube) | 3-8 进阶 | ⭐⭐⭐⭐ |
| Dan Abramov 的 Blog | 深入原理 | ⭐⭐⭐⭐⭐ |
| Kent C. Dodds - Epic React | 系统性 | ⭐⭐⭐⭐⭐ |
| TanStack Query 官方文档 | 6 | ⭐⭐⭐⭐ |
| Zustand 官方文档 | 7 | ⭐⭐⭐⭐ |
| [react.dev/reference](https://react.dev/reference) | 速查 | ⭐⭐⭐⭐⭐ |

---

## 学习建议

```
1. 从 react.dev 的交互式教程开始，边看边写
2. 理解心智模型（UI = f(state) + 渲染机制）比记 API 重要 100 倍
3. 阶段 3（Hooks）是核心中的核心，必须完全理解
4. 从阶段 4 开始直接用 TypeScript，不走回头路
5. 遇到 "怎么实现 X" → 先想 "state 怎么设计"，不是 "DOM 怎么操作"
6. 性能优化：先用 DevTools 测量确认有问题，再优化。不要过早优化
7. 和你的 Vue 经验对比学习，找到「同一个问题不同解法」的规律
```

---

> **最终目标**：能在实际工作中自信地用 React + TypeScript 开发功能，理解每一行代码为什么这么写。阶段 3 吃透 Hooks 后你就找回来了，阶段 5-7 让你能独立搞定复杂场景。
