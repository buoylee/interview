# 阶段 7：状态管理 + 性能优化（2 天）

> **一句话定位**：合为一个阶段，因为它们紧密相关——状态管理的核心问题就是"如何高效地让该更新的更新，不该更新的不更新"。

---

## 目录

- [1. 状态分层](#1-状态分层)
- [2. Zustand：全局状态管理](#2-zustand全局状态管理)
- [3. 渲染机制回顾](#3-渲染机制回顾)
- [4. React.memo](#4-reactmemo)
- [5. useMemo](#5-usememo)
- [6. useCallback](#6-usecallback)
- [7. 三者配合使用](#7-三者配合使用)
- [8. React DevTools](#8-react-devtools)
- [9. 性能优化原则](#9-性能优化原则)
- [10. 面试常问](#10-面试常问)
- [11. 练习](#11-练习)

---

## 1. 状态分层

### 1.1 状态分层金字塔

```
不是所有状态都需要"状态管理库"！
大部分状态是 local state 或 server state，真正需要全局 UI state 的很少。

                 ┌──────────────────────┐
                 │   URL State          │  ← React Router（路由参数、查询字符串）
                 │   (路由状态)          │     /users?page=2&sort=name
                 ├──────────────────────┤
                 │   Server State       │  ← TanStack Query（API 数据 + 缓存）
                 │   (服务端数据)        │     用户列表、商品数据、订单...
                 ├──────────────────────┤
                 │   Global UI State    │  ← Zustand / Context
                 │   (全局 UI 状态)      │     主题、语言、侧边栏开关、通知
                 ├──────────────────────┤
                 │   Local UI State     │  ← useState（最多的一层）
                 │   (组件局部状态)      │     表单输入、modal 开关、tab 选中
                 └──────────────────────┘
```

### 1.2 决策指南

```
你的状态应该放哪里？

  "输入框的值、modal 是否打开、当前选中的 tab"
    → useState（组件局部）

  "API 返回的用户列表、商品详情"
    → TanStack Query（服务端状态）

  "当前主题、语言设置、用户认证状态、全局通知"
    → Zustand（或 Context，如果变化频率低）

  "当前 URL 路径、页码、排序方式"
    → React Router（URL 状态）

  ⭐ 常见错误：把所有东西都放进全局 store
  → 大部分状态就该是 local 的，全局化反而增加复杂度
```

---

## 2. Zustand：全局状态管理

### 2.1 为什么选 Zustand

```
主流方案对比：

  Redux：功能最多，但样板代码太多（action + reducer + dispatch + selector）
  MobX：响应式，类似 Vue 的思维，但 React 社区用得少
  Zustand：极简 API + 原生支持 React + 自动按需渲染
  Jotai/Recoil：原子化状态，适合细粒度的独立状态

  ⭐ 2024-2025 趋势：Zustand 已成为 React 全局状态管理的首选
  理由：零 boilerplate、无 Provider、自动按需渲染、TS 支持好
```

### 2.2 基本用法

```bash
npm install zustand
```

```tsx
import { create } from 'zustand'

// ① 定义 Store
interface AppStore {
  // 状态
  theme: 'light' | 'dark'
  sidebarOpen: boolean
  notifications: string[]

  // 操作
  toggleTheme: () => void
  toggleSidebar: () => void
  addNotification: (msg: string) => void
  clearNotifications: () => void
}

const useAppStore = create<AppStore>((set) => ({
  // 初始状态
  theme: 'light',
  sidebarOpen: true,
  notifications: [],

  // 操作（通过 set 更新状态）
  toggleTheme: () => set(s => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),
  toggleSidebar: () => set(s => ({ sidebarOpen: !s.sidebarOpen })),
  addNotification: (msg) => set(s => ({ notifications: [...s.notifications, msg] })),
  clearNotifications: () => set({ notifications: [] }),
}))
```

### 2.3 在组件中使用

```tsx
// ⭐ 核心用法：选择性订阅（只读你需要的字段）
function Header() {
  const theme = useAppStore(s => s.theme)           // 只订阅 theme
  const toggleTheme = useAppStore(s => s.toggleTheme)

  return <button onClick={toggleTheme}>当前: {theme}</button>
}
// theme 变化时 → Header 重新渲染
// sidebarOpen 变化时 → Header 不重新渲染（因为它没订阅 sidebarOpen）
// ↑ 这就是 Zustand 比 Context 好的地方：自动按需渲染

function Sidebar() {
  const isOpen = useAppStore(s => s.sidebarOpen)    // 只订阅 sidebarOpen

  if (!isOpen) return null
  return <aside>侧边栏内容</aside>
}
```

### 2.4 Zustand vs Context

```
                    Context               Zustand
设置               需要 Provider 包裹      不需要
订阅粒度            整个 value             单个字段
渲染性能            value 变了→所有消费者渲染  只有读了该字段的组件渲染
代码量              多（Context+Provider+Hook） 少（一个 create 搞定）
适用场景            少量低频数据（主题）     任何全局 UI 状态

⭐ 经验法则：
  小项目/数据很少 → Context 够用
  中大项目/性能敏感 → Zustand
```

### 2.5 Zustand 进阶

```tsx
// ① 在 store 外读取状态（不在组件里）
const currentTheme = useAppStore.getState().theme

// ② 订阅变化（不在组件里，如日志）
useAppStore.subscribe((state) => {
  console.log('状态变化:', state)
})

// ③ 持久化（自动存 localStorage）
import { persist } from 'zustand/middleware'

const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      theme: 'light',
      language: 'zh',
      toggleTheme: () => set(s => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),
    }),
    { name: 'settings-storage' }   // localStorage key
  )
)
```

---

## 3. 渲染机制回顾

```
回到阶段 1 的渲染主线——现在我们来学如何优化它。

⭐ 组件什么时候会重新渲染？
  1. 自己的 state 变了
  2. 父组件重新渲染了（即使自己的 props 没变！）← 最常见的"不必要渲染"
  3. 消费的 Context value 变了

⭐ 渲染 ≠ DOM 更新
  渲染 = 调用组件函数 + 生成虚拟 DOM（有计算开销）
  DOM 更新 = diff 后发现变化时才更新真实 DOM

  优化目标：减少不必要的"渲染"（减少函数调用和虚拟 DOM 生成）
```

---

## 4. React.memo

### 4.1 作用

```
React.memo = 包裹一个组件，让它在 props 没变的时候跳过渲染

  默认行为：父组件渲染 → 子组件也渲染（不管 props 变没变）
  用 memo 后：父组件渲染 → 对比 props → 没变 → 跳过子组件渲染
```

### 4.2 用法

```tsx
import { memo } from 'react'

// 包裹组件
const TodoItem = memo(function TodoItem({ todo, onDelete }: TodoItemProps) {
  console.log('TodoItem 渲染:', todo.id)  // 用来观察是否渲染
  return (
    <li>
      {todo.text}
      <button onClick={() => onDelete(todo.id)}>删除</button>
    </li>
  )
})

// 现在 TodoItem 只有在 todo 或 onDelete 变化时才渲染
// 如果父组件因为其他 state 变化而渲染，TodoItem 不会跟着渲染（如果 props 没变的话）
```

### 4.3 memo 失效的常见原因

```tsx
function TodoApp() {
  const [todos, setTodos] = useState<Todo[]>([])

  // ❌ 每次渲染都创建新函数 → memo 认为 props 变了 → 失效
  return (
    <ul>
      {todos.map(todo => (
        <TodoItem
          key={todo.id}
          todo={todo}
          onDelete={(id) => setTodos(prev => prev.filter(t => t.id !== id))}
          //        ↑ 每次渲染都是新函数引用 → Object.is 比较不相等 → memo 无效
        />
      ))}
    </ul>
  )
}

// ⭐ memo 只做浅比较（Object.is）：
//   基本类型（string, number, boolean）→ 值相同就相等
//   引用类型（对象, 数组, 函数）→ 引用相同才相等
//   每次渲染创建的新对象/函数 → 引用不同 → memo 认为 props 变了
//   → 这就是为什么需要 useCallback 和 useMemo
```

---

## 5. useMemo

### 5.1 作用

```
useMemo = 缓存一个计算结果，只在依赖变化时重新计算

  没有 useMemo：每次渲染都计算 → 如果计算很昂贵，浪费性能
  有了 useMemo：依赖没变 → 直接返回上次的结果，跳过计算
```

### 5.2 用法

```tsx
function TodoApp() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [filter, setFilter] = useState<'all' | 'done' | 'undone'>('all')
  const [searchText, setSearchText] = useState('')

  // ✅ 缓存计算结果：只在 todos 或 filter 变化时重新计算
  const filteredTodos = useMemo(() => {
    console.log('重新计算 filteredTodos')  // 观察是否执行
    return todos.filter(t =>
      filter === 'all' ? true : filter === 'done' ? t.done : !t.done
    )
  }, [todos, filter])
  // searchText 变化时 → 不重新计算（因为不在依赖里）

  return (/* ... */)
}
```

### 5.3 什么时候用 useMemo

```
✅ 应该用的场景：
  → 昂贵的计算（大数组排序/过滤、复杂的数据转换）
  → 传给 memo 组件的对象/数组 prop（稳定引用）
  → 用作其他 Hook 的依赖项

❌ 不需要用的场景：
  → 简单的计算（a + b, arr.length）
  → 基本类型的值（string, number）
  → 只渲染一次或很少渲染的组件

⭐ 不确定时，先不用。用 DevTools Profiler 确认有性能问题后再加
```

---

## 6. useCallback

### 6.1 作用

```
useCallback = 缓存一个函数引用，只在依赖变化时创建新函数

  本质是 useMemo 的语法糖：
  useCallback(fn, deps) === useMemo(() => fn, deps)

  主要用途：配合 React.memo 使用
  → 让 memo 包裹的子组件不会因为"函数引用变了"而重新渲染
```

### 6.2 用法

```tsx
function TodoApp() {
  const [todos, setTodos] = useState<Todo[]>([])

  // ✅ 缓存函数引用
  const handleDelete = useCallback((id: number) => {
    setTodos(prev => prev.filter(t => t.id !== id))
  }, [])  // 空依赖：函数永远不会重新创建
  // 注意这里用了函数式更新 prev => ...
  // 所以不需要把 todos 放入依赖

  const handleToggle = useCallback((id: number) => {
    setTodos(prev => prev.map(t =>
      t.id === id ? { ...t, done: !t.done } : t
    ))
  }, [])

  return (
    <ul>
      {todos.map(todo => (
        <TodoItem
          key={todo.id}
          todo={todo}
          onDelete={handleDelete}    // 引用稳定 → memo 有效
          onToggle={handleToggle}    // 引用稳定 → memo 有效
        />
      ))}
    </ul>
  )
}
```

### 6.3 什么时候用 useCallback

```
✅ 应该用的场景：
  → 传给 React.memo 包裹的子组件的回调函数
  → 用作 useEffect 依赖项的函数
  → 传给自定义 Hook 的回调

❌ 不需要用的场景：
  → 没有配合 memo 使用（缓存了也没意义）
  → 内联的简单事件处理（<button onClick={() => ...}>）
  → 组件只渲染一次或很少渲染

⭐ useCallback 单独用没有意义！必须配合 React.memo 才有效果
```

---

## 7. 三者配合使用

### 7.1 完整示例

```tsx
import { useState, useMemo, useCallback, memo } from 'react'

// ① memo 包裹子组件
const TodoItem = memo(function TodoItem({ todo, onToggle, onDelete }: TodoItemProps) {
  console.log('TodoItem 渲染:', todo.id)
  return (
    <li style={{ textDecoration: todo.done ? 'line-through' : 'none' }}>
      <span onClick={() => onToggle(todo.id)}>{todo.text}</span>
      <button onClick={() => onDelete(todo.id)}>删除</button>
    </li>
  )
})

function TodoApp() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [filter, setFilter] = useState<'all' | 'done' | 'undone'>('all')

  // ② useMemo 缓存计算结果
  const filteredTodos = useMemo(
    () => todos.filter(t =>
      filter === 'all' ? true : filter === 'done' ? t.done : !t.done
    ),
    [todos, filter]
  )

  // ③ useCallback 缓存函数引用（配合 memo）
  const handleToggle = useCallback((id: number) => {
    setTodos(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t))
  }, [])

  const handleDelete = useCallback((id: number) => {
    setTodos(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <div>
      <TodoFilter filter={filter} onFilterChange={setFilter} />
      <ul>
        {filteredTodos.map(todo => (
          <TodoItem
            key={todo.id}
            todo={todo}                 // todo 对象引用在 filter 变化时不变
            onToggle={handleToggle}     // 函数引用稳定 ✅
            onDelete={handleDelete}     // 函数引用稳定 ✅
          />
        ))}
      </ul>
    </div>
  )
}

// 效果：
// 修改 filter → filteredTodos 重新计算 → 但每个 TodoItem 的 props 没变 → 跳过渲染
// 删除一个 todo → todos 变了 → 被删的 TodoItem 消失 → 其他 TodoItem props 没变 → 跳过渲染
```

---

## 8. React DevTools

### 8.1 安装与基本功能

```
1. 安装 React DevTools 浏览器扩展（Chrome/Firefox）
2. 打开开发者工具 → 出现 "Components" 和 "Profiler" 两个新面板

Components 面板：
  → 查看组件树结构
  → 点击任何组件查看当前 props / state / hooks 值
  → 实时编辑 state 值观察变化

  ⭐ 勾选 Settings → "Highlight updates when components render"
  → 渲染的组件会闪烁边框
  → 你会直观看到哪些组件在"不必要地"渲染
```

### 8.2 Profiler 使用

```
Profiler 面板（最重要的性能工具）：

  1. 点击 "Record" 按钮
  2. 在页面上操作（点击、输入、切换...）
  3. 点击 "Stop"
  4. 查看每次渲染的信息：
     → 哪些组件渲染了
     → 每个组件渲染耗时
     → 为什么渲染（"Why did this render?"需在设置中开启）

  读懂 Profiler 的结果：
    绿色 → 渲染了但很快（没问题）
    黄色 → 渲染耗时较长（关注）
    灰色 → 没有渲染（被 memo 跳过了）

  ⭐ 优化流程：
    1. 用 Profiler 录制 → 找到渲染频繁/耗时长的组件
    2. 分析"Why did this render?" → 找到原因
    3. 对症下药：memo / useMemo / useCallback / 状态下移
    4. 再次录制 → 对比优化前后
```

---

## 9. 性能优化原则

### 9.1 优化顺序（优先级从高到低）

```
1. 状态下移
   → 把频繁变化的 state 放到更小的子组件里
   → 父组件不因子组件的 state 变化而重新渲染
   → 零额外代码，最简单有效

2. 内容提升（children 模式）
   → 把不会变的 JSX 通过 children 传入
   → 父组件渲染时 children 引用不变 → 跳过

3. React.memo
   → 包裹纯展示组件
   → 配合 useCallback / useMemo 稳定 props

4. useMemo / useCallback
   → 缓存昂贵计算 / 函数引用
   → 必须配合 memo 才有效

5. 虚拟列表
   → 大列表（>500 条）用 react-window 或 react-virtuoso
   → 只渲染可视区域内的元素

6. 代码分割 + 懒加载
   → React.lazy + Suspense
   → 按路由或大组件拆分 bundle
```

### 9.2 不要做的事

```
❌ 过早优化
  → 大多数组件不需要 memo/useMemo/useCallback
  → React 的 diff 已经够快了
  → 先写正确的代码，有性能问题时再优化

❌ 到处加 memo
  → memo 本身有开销（对比 props）
  → 如果 props 每次都变（对象字面量），memo 白加了还多了开销
  → 只在 Profiler 确认有问题时加

❌ 用 useMemo 缓存简单计算
  → const total = useMemo(() => a + b, [a, b]) ← 过度优化
  → const total = a + b ← 这就够了

⭐ 黄金法则：先测量，后优化
  "You can't optimize what you can't measure"
```

---

## 10. 面试常问

### Q1: React 组件什么时候会重新渲染？

**答**：
1. 自己的 state 变了（setState）
2. 父组件重新渲染了（不管 props 变没变——这是最常见的不必要渲染来源）
3. 消费的 Context value 变了
- 注意：props 变化本身不直接触发渲染，是父组件渲染导致子组件跟着渲染

### Q2: React.memo、useMemo、useCallback 分别是什么？

**答**：

| | 缓存什么 | 用途 |
|--|---------|------|
| React.memo | 组件的渲染结果 | props 没变就跳过渲染 |
| useMemo | 计算的返回值 | 避免昂贵计算重复执行 |
| useCallback | 函数引用 | 配合 memo，避免因"新函数引用"导致子组件重新渲染 |

- useCallback 单独用没意义，必须配合 memo
- 三者都不是越多越好，应该在确认有性能问题后才使用

### Q3: Context 的性能问题和 Zustand 的优势？

**答**：
- Context：value 变化 → 所有消费者组件重新渲染（即使只用了一部分）
- Zustand：选择性订阅（`useStore(s => s.theme)`），只有读了 theme 的组件因 theme 变化而渲染
- Zustand 还不需要 Provider 包裹，代码更简洁

### Q4: 怎么排查和优化 React 性能问题？

**答**：
1. **React DevTools Profiler** 录制操作 → 找到渲染频繁/慢的组件
2. 开启 "Why did this render?" → 找到渲染原因
3. 按优先级优化：状态下移 > memo > useMemo/useCallback > 虚拟列表
4. 再次录制对比优化前后
5. 原则：先测量后优化，不要过早优化

---

## 11. 练习

```
状态管理：
  1. 用 Zustand 创建一个 AppStore（主题 + 侧边栏 + 通知）
     → 在 3 个组件中分别订阅不同字段
     → 验证：修改 theme 时，只读了 theme 的组件渲染

  2. 用 Zustand 的 persist 中间件实现主题持久化
     → 刷新页面后主题设置不丢失

性能优化：
  3. 安装 React DevTools
     → 对你的 TodoApp 开启 "Highlight updates"
     → 操作页面，观察哪些组件在不必要地渲染

  4. 用 Profiler 录制 TodoApp 的操作
     → 找出"输入框每次击键导致所有 TodoItem 渲染"的问题
     → 用 React.memo + useCallback 优化
     → 再次录制，对比优化前后

  5. 构造一个"昂贵计算"场景
     → 一个列表有 1000 条数据 + 排序/过滤
     → 不用 useMemo → 观察输入框卡顿
     → 加 useMemo → 观察恢复流畅
```

---

## 📖 推荐学习路径

1. [Zustand 官方文档](https://zustand-demo.pmnd.rs/) — 10 分钟上手
2. [react.dev - Extracting State Logic into a Reducer](https://react.dev/learn/extracting-state-logic-into-a-reducer)
3. 用 React DevTools Profiler 分析你之前写的 TodoApp
4. 核心：先学会用 DevTools 测量，再学优化手段

> ⬅️ [上一阶段：路由 + 数据层](./06-routing-data.md) | ➡️ [下一阶段：现代 React 生态 + 实战](./08-modern-react.md)
