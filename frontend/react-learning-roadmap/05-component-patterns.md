# 阶段 5：组件设计 & 复用模式（1-2 天）

> **一句话定位**：学会把代码组织得优雅——从"能用"到"好用"。核心是自定义 Hook（逻辑复用）和组合模式（UI 复用）。

---

## 目录

- [1. 组件设计思维](#1-组件设计思维)
- [2. 受控 vs 非受控](#2-受控-vs-非受控)
- [3. 自定义 Hook](#3-自定义-hook)
- [4. 组合模式与 children](#4-组合模式与-children)
- [5. 关注点分离](#5-关注点分离)
- [6. 常用自定义 Hook 实战](#6-常用自定义-hook-实战)
- [7. 模式决策树](#7-模式决策树)
- [8. 面试常问](#8-面试常问)
- [9. 练习](#9-练习)

---

## 1. 组件设计思维

### 1.1 好组件的标准

```
一个好组件应该满足：

  单一职责 → 只做一件事
    ❌ UserCardWithEditFormAndNotification
    ✅ UserCard + EditForm + Notification

  可预测 → 同样的 props → 同样的输出
    ❌ 内部依赖全局变量或时间
    ✅ 所有数据都来自 props 或自己的 state

  可组合 → 能和其他组件灵活组合
    ❌ 内部硬编码了子组件
    ✅ 用 children 让外部决定内容

  可复用 → 换个场景也能用
    ❌ Button 里硬编码了"提交订单"
    ✅ Button 接受 text prop，通用
```

### 1.2 何时拆分组件

```
信号          → 动作
──────────    ──────────
组件超过 150 行    → 拆！
有独立的功能区域    → 拆成独立组件
同样的 UI 出现 2+ 次 → 提取为可复用组件
状态逻辑可独立     → 提取为自定义 Hook
又有数据逻辑又有 UI → 用 Hook 分离逻辑

不要拆的情况：
  → 只为了"文件小"而拆（增加了理解成本，没有简化逻辑）
  → 组件只在一处使用且逻辑简单
```

---

## 2. 受控 vs 非受控

### 2.1 受控组件（推荐）

```tsx
// 受控 = React state 管理表单值
function ControlledInput() {
  const [value, setValue] = useState('')

  return (
    <input
      value={value}                          // React 控制显示什么
      onChange={e => setValue(e.target.value)} // 用户输入 → 更新 state → 重新渲染
    />
  )
  // 数据流：用户输入 → onChange → setState → 重新渲染 → input 显示新值
  // React 是"单一数据源"：state 里的值就是 input 显示的值
}

// 受控组件的能力：
function ControlledDemo() {
  const [value, setValue] = useState('')

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    // ✅ 可以在此做任何处理：
    setValue(newValue.toUpperCase())         // 强制大写
    // setValue(newValue.slice(0, 10))       // 限制长度
    // setValue(newValue.replace(/\D/g, '')) // 只允许数字
  }

  return <input value={value} onChange={handleChange} />
}
```

### 2.2 非受控组件

```tsx
// 非受控 = DOM 自己管理值，React 只在需要时读取
function UncontrolledInput() {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = () => {
    // 通过 ref 从 DOM 读取值
    console.log(inputRef.current?.value)
  }

  return (
    <>
      <input ref={inputRef} defaultValue="初始值" />
      {/*                   ↑ defaultValue 不是 value */}
      <button onClick={handleSubmit}>提交</button>
    </>
  )
}

// 非受控的场景：
// - 文件上传 <input type="file" />（值只能由用户设置，无法程序控制）
// - 集成第三方 DOM 库
// - 简单表单，不需要实时验证
```

### 2.3 怎么选

```
                需要实时控制输入值吗？
               （验证、格式化、联动）
                       │
               ┌───────┴───────┐
               是              否
               ↓               ↓
          受控组件          只需要提交时读取值吗？
        value+onChange          │
                       ┌───────┴───────┐
                       是              否
                       ↓               ↓
                  非受控组件         受控组件
                defaultValue+ref   （默认选受控）

  ⭐ 经验法则：绝大多数情况用受控组件
  Vue 的 v-model 本质就是受控（value+onInput 语法糖）
```

---

## 3. 自定义 Hook

### 3.1 什么是自定义 Hook

```
自定义 Hook = 以 use 开头的函数 + 内部调用其他 Hook

核心价值：
  把"有状态的逻辑"从组件中抽出来
  → 多个组件可以复用同一段逻辑
  → 组件变得更干净（只剩 UI）

和普通函数的区别：
  普通函数：只能做无状态的计算（formatDate、sortArray）
  自定义 Hook：可以包含 state、effect、ref 等有状态的逻辑

和 Vue composables 的对比：
  React 自定义 Hook ≈ Vue composables（如 useCounter、useFetch）
  思想完全一致，只是语法不同
```

### 3.2 从组件中提取 Hook

```tsx
// ————— 重构前：逻辑和 UI 混在一起 —————
function UserProfile({ userId }: { userId: number }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`/api/users/${userId}`)
      .then(res => res.json())
      .then(data => { if (!cancelled) { setUser(data); setLoading(false) } })
      .catch(err => { if (!cancelled) { setError(err.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [userId])

  if (loading) return <Spinner />
  if (error) return <ErrorMessage message={error} />
  return <div>{user?.name}</div>
}

// ————— 重构后：逻辑提取到 Hook —————
// 自定义 Hook：可在任何组件中复用
function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(url)
      .then(res => { if (!res.ok) throw new Error('请求失败'); return res.json() })
      .then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [url])

  return { data, loading, error }
}

// 组件：只剩 UI
function UserProfile({ userId }: { userId: number }) {
  const { data: user, loading, error } = useFetch<User>(`/api/users/${userId}`)

  if (loading) return <Spinner />
  if (error) return <ErrorMessage message={error} />
  return <div>{user?.name}</div>
}

// 另一个组件也能复用同一个 Hook！
function ProductList() {
  const { data: products, loading } = useFetch<Product[]>('/api/products')
  if (loading) return <Spinner />
  return <ul>{products?.map(p => <li key={p.id}>{p.name}</li>)}</ul>
}
```

### 3.3 自定义 Hook 的规则

```
1. 必须以 use 开头
   ✅ useFetch, useLocalStorage, useDebounce
   ❌ fetchData, getFromStorage

   为什么？React 和 ESLint 靠 use 前缀识别 Hook，
   确保它遵守 Hooks 规则（不在条件/循环中调用）

2. 内部必须调用至少一个 React Hook
   如果不调用任何 Hook → 它就是普通函数，不需要 use 前缀

3. 和组件一样，只能在顶层调用
   ❌ if (condition) { useFetch(...) }
```

---

## 4. 组合模式与 children

### 4.1 children 基本用法

```tsx
// children 是 React 最自然的"插槽"机制

interface CardProps {
  title: string
  children: React.ReactNode
}

function Card({ title, children }: CardProps) {
  return (
    <div className="card">
      <div className="card-header"><h3>{title}</h3></div>
      <div className="card-body">{children}</div>
    </div>
  )
}

// 使用：内容完全由调用方决定
<Card title="用户信息">
  <Avatar url={user.avatar} />
  <p>{user.bio}</p>
</Card>

<Card title="统计数据">
  <Chart data={stats} />
</Card>
```

### 4.2 多插槽模式

```tsx
// React 没有 Vue 的 <slot name="xxx">，但有更灵活的方式：

interface PageLayoutProps {
  header: React.ReactNode
  sidebar: React.ReactNode
  children: React.ReactNode      // 默认插槽
  footer?: React.ReactNode       // 可选插槽
}

function PageLayout({ header, sidebar, children, footer }: PageLayoutProps) {
  return (
    <div className="page">
      <header>{header}</header>
      <div className="content">
        <aside>{sidebar}</aside>
        <main>{children}</main>
      </div>
      {footer && <footer>{footer}</footer>}
    </div>
  )
}

// 使用
<PageLayout
  header={<Navbar />}
  sidebar={<Menu items={menuItems} />}
  footer={<Copyright />}
>
  <ArticleList articles={articles} />
</PageLayout>
```

### 4.3 Render Props 模式（了解即可）

```tsx
// Render Props = 把"怎么渲染"作为 prop 传进去
// 现在较少用（已被自定义 Hook 取代），但老代码里可能会看到

interface MouseTrackerProps {
  render: (pos: { x: number; y: number }) => React.ReactNode
}

function MouseTracker({ render }: MouseTrackerProps) {
  const [pos, setPos] = useState({ x: 0, y: 0 })
  useEffect(() => {
    const handler = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY })
    window.addEventListener('mousemove', handler)
    return () => window.removeEventListener('mousemove', handler)
  }, [])
  return <>{render(pos)}</>
}

// 使用
<MouseTracker render={({ x, y }) => <p>鼠标在 ({x}, {y})</p>} />

// ✅ 现代替代：用自定义 Hook
function useMousePosition() {
  const [pos, setPos] = useState({ x: 0, y: 0 })
  useEffect(() => {
    const handler = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY })
    window.addEventListener('mousemove', handler)
    return () => window.removeEventListener('mousemove', handler)
  }, [])
  return pos
}

function MyComponent() {
  const { x, y } = useMousePosition()   // 更简洁
  return <p>鼠标在 ({x}, {y})</p>
}
```

---

## 5. 关注点分离

### 5.1 逻辑 vs UI 分离

```
原则：自定义 Hook 管理"做什么"，组件管理"长什么样"

  ❌ 混在一起：
  function TodoApp() {
    const [todos, setTodos] = useState([])
    const [filter, setFilter] = useState('all')
    const handleAdd = (text) => { ... }
    const handleToggle = (id) => { ... }
    const handleDelete = (id) => { ... }
    const filteredTodos = todos.filter(...)
    // 50 行逻辑代码...

    return (
      // 50 行 JSX 代码...
    )
  }

  ✅ 分离：
  // Hook 管数据逻辑
  function useTodos() {
    const [todos, setTodos] = useState<Todo[]>([])
    const [filter, setFilter] = useState<Filter>('all')

    const add = (text: string) => { ... }
    const toggle = (id: number) => { ... }
    const remove = (id: number) => { ... }
    const filtered = todos.filter(...)

    return { todos: filtered, filter, add, toggle, remove, setFilter }
  }

  // 组件只管 UI
  function TodoApp() {
    const { todos, filter, add, toggle, remove, setFilter } = useTodos()

    return (
      // 干净的 JSX，没有逻辑代码
    )
  }
```

### 5.2 什么适合提取成 Hook

```
适合提取的逻辑：
  ✅ 数据请求（useFetch, useQuery）
  ✅ 表单管理（useForm）
  ✅ 防抖/节流（useDebounce, useThrottle）
  ✅ 本地存储（useLocalStorage）
  ✅ 窗口尺寸/滚动位置（useWindowSize, useScroll）
  ✅ 定时器管理（useInterval, useTimeout）
  ✅ 业务逻辑（useTodos, useCart, useAuth）

不适合提取的情况：
  ❌ 纯 UI 逻辑（展开/折叠一个 div 用 useState 就够了）
  ❌ 只在一个地方用且只有 1-2 行的逻辑
```

---

## 6. 常用自定义 Hook 实战

### 6.1 useLocalStorage

```tsx
function useLocalStorage<T>(key: string, initialValue: T) {
  // 惰性初始化：从 localStorage 读取
  const [value, setValue] = useState<T>(() => {
    try {
      const item = localStorage.getItem(key)
      return item ? JSON.parse(item) : initialValue
    } catch {
      return initialValue
    }
  })

  // 值变化时写入 localStorage
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(value))
  }, [key, value])

  return [value, setValue] as const
  //                       ↑ as const 让返回类型是 [T, SetState<T>]，不是 (T | SetState<T>)[]
}

// 使用
function App() {
  const [theme, setTheme] = useLocalStorage('theme', 'light')
  const [todos, setTodos] = useLocalStorage<Todo[]>('todos', [])
  // 自动读取/写入 localStorage，组件不用关心存储细节
}
```

### 6.2 useDebounce

```tsx
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
    // value 变化 → 设置定时器 → delay ms 后更新
    // 如果在 delay ms 内 value 又变了 → 清除旧定时器 → 设置新定时器
    // 效果：只有用户停止输入 delay ms 后才更新
  }, [value, delay])

  return debouncedValue
}

// 使用：搜索防抖
function SearchBox() {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebounce(query, 300)  // 300ms 防抖

  const { data } = useFetch<Result[]>(
    debouncedQuery ? `/api/search?q=${debouncedQuery}` : null
  )

  return (
    <div>
      <input value={query} onChange={e => setQuery(e.target.value)} />
      {/* 用户每次击键都更新 query（input 即时响应） */}
      {/* 但 API 请求用的是 debouncedQuery（300ms 防抖后才请求） */}
    </div>
  )
}
```

### 6.3 useToggle

```tsx
function useToggle(initialValue = false) {
  const [value, setValue] = useState(initialValue)

  const toggle = useCallback(() => setValue(v => !v), [])
  const setTrue = useCallback(() => setValue(true), [])
  const setFalse = useCallback(() => setValue(false), [])

  return { value, toggle, setTrue, setFalse }
}

// 使用
function Modal() {
  const { value: isOpen, toggle, setFalse: close } = useToggle()

  return (
    <>
      <button onClick={toggle}>打开</button>
      {isOpen && (
        <div className="modal">
          <p>Modal 内容</p>
          <button onClick={close}>关闭</button>
        </div>
      )}
    </>
  )
}
```

---

## 7. 模式决策树

```
你要解决什么问题？

  "表单元素的值由谁管？"
    → React 管（推荐）→ 受控组件：value + onChange
    → DOM 管            → 非受控组件：defaultValue + ref

  "多个组件有相同的状态逻辑"
    → 提取自定义 Hook → useFetch, useForm, useDebounce...

  "组件需要灵活的内部结构"
    → 用 children 作为默认插槽
    → 用 Props 传 ReactNode 作为具名插槽

  "组件既有数据逻辑又有 UI"
    → 用自定义 Hook 分离逻辑

  "需要一个通用容器（Card, Modal, Layout）"
    → 用 children + 组合模式

  "状态应该放在哪个层级？"
    → 只有一个组件用 → 放在该组件里
    → 兄弟组件需要共享 → 提升到父组件
    → 很多组件需要 → useContext 或 Zustand（阶段 7）
```

---

## 8. 面试常问

### Q1: 什么是自定义 Hook？它和普通函数有什么区别？

**答**：
- 自定义 Hook 是以 `use` 开头的函数，内部调用了其他 React Hook（useState、useEffect 等）
- 和普通函数的区别：自定义 Hook 可以包含有状态的逻辑（state、effect、ref），普通函数只能做无状态计算
- 核心价值：实现"有状态逻辑"的复用——多个组件可以共享同一段包含 state 和 effect 的逻辑
- 注意：每次调用自定义 Hook 都创建独立的 state，不是共享同一份 state

### Q2: 受控组件和非受控组件怎么选？

**答**：
- **受控**：React state 管理 value，通过 onChange 更新。适合需要实时控制输入的场景（验证、格式化、联动）
- **非受控**：DOM 管理值，通过 ref 在需要时读取。适合简单表单、文件上传
- 默认选受控，只有特殊原因才用非受控

### Q3: React 的组合模式是什么？和 Vue 的 slot 有什么异同？

**答**：
- React 用 `children` prop + JSX 嵌套实现组合，本质和 Vue 的 `<slot>` 相同
- children = Vue 的默认 slot；用 Props 传 ReactNode = Vue 的具名 slot
- 区别：React 的组合更灵活（children 可以是任何 JS 值），Vue 的 slot 语法更声明式
- React 没有"作用域插槽"（scoped slot），但可以用 Render Props 或自定义 Hook 替代

---

## 9. 练习

```
自定义 Hook：
  1. 写 useLocalStorage<T>(key, initialValue)
     → 自动读写 localStorage + 状态同步
     → 用 as const 确保返回类型正确

  2. 写 useDebounce<T>(value, delay)
     → 搭配一个搜索输入框测试

  3. 把阶段 2 的 TodoApp 逻辑提取成 useTodos Hook
     → Hook 返回 { todos, add, toggle, remove, filter, setFilter }
     → 组件只保留 JSX
     → 对比重构前后的代码清晰度

组合模式：
  4. 写一个 Modal 组件
     → 接受 isOpen, onClose, title, children
     → 点击遮罩层关闭
     → 用组合模式，Modal 内部可以放任意内容

  5. 写一个 PageLayout 组件
     → 接受 header, sidebar, children, footer（多插槽）
     → 在你的 TodoApp 中使用

综合：
  6. 把上述练习中所有的组件和 Hook 串起来：
     → useTodos 管理数据
     → useLocalStorage 持久化
     → Modal 组件用于"确认删除"
     → PageLayout 组织页面结构
```

---

## 📖 推荐学习路径

1. 阅读 [react.dev - Reusing Logic with Custom Hooks](https://react.dev/learn/reusing-logic-with-custom-hooks)
2. 浏览 [usehooks.com](https://usehooks.com/) — 精选自定义 Hook 合集
3. 核心：亲手写 useFetch + useLocalStorage + useDebounce 这 3 个 Hook，覆盖了 90% 的模式

> ⬅️ [上一阶段：TypeScript + React](./04-typescript-react.md) | ➡️ [下一阶段：路由 + 数据层](./06-routing-data.md)
