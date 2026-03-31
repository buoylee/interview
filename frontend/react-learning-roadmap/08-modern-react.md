# 阶段 8：现代 React 生态 + 实战（2-3 天）

> **一句话定位**：了解 React 19 新特性和 Server Components 生态，然后通过 3 个递进项目巩固全部所学。前 7 个阶段学的是"肌肉"，这个阶段把它们组合成"动作"。

---

## 目录

- [1. Suspense + ErrorBoundary（前置知识）](#1-suspense--errorboundary前置知识)
- [2. React 19 新特性](#2-react-19-新特性)
- [3. Server Components 简介](#3-server-components-简介)
- [4. 元框架：Next.js](#4-元框架nextjs)
- [5. 生态速览](#5-生态速览)
- [6. 练习：实战项目](#6-练习实战项目)
- [7. 面试常问](#7-面试常问)

---

## 1. Suspense + ErrorBoundary（前置知识）

### 1.1 Suspense：等待异步内容

```tsx
import { Suspense } from 'react'

// Suspense 让你声明"在子组件加载时显示什么"
<Suspense fallback={<Spinner />}>
  <AsyncComponent />   {/* 在加载完成前，显示 <Spinner /> */}
</Suspense>

// ⭐ Suspense 不是自己发请求
// 它只是一个"等待边界"——子组件告诉 React 它还没准备好时，Suspense 显示 fallback

// 什么能触发 Suspense：
//   - React.lazy 加载的组件（代码分割）
//   - 使用 React 19 的 use() 读取 Promise
//   - TanStack Query 的 suspense 模式
//   - 任何能"挂起"的数据源
```

### 1.2 Suspense 实现代码分割

```tsx
import { lazy, Suspense } from 'react'

// ① lazy 动态导入组件
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Settings = lazy(() => import('./pages/Settings'))
// 只有当组件真正要渲染时才开始加载对应的 JS 文件

// ② Suspense 提供加载状态
function App() {
  return (
    <Routes>
      <Route path="/dashboard" element={
        <Suspense fallback={<div>加载中...</div>}>
          <Dashboard />
        </Suspense>
      } />
      <Route path="/settings" element={
        <Suspense fallback={<Spinner />}>
          <Settings />
        </Suspense>
      } />
    </Routes>
  )
}

// 效果：
// 首次加载页面时不会下载 Dashboard 和 Settings 的代码
// 用户导航到 /dashboard 时 → 下载 Dashboard 的代码 → 显示 Spinner → 加载完显示 Dashboard
// ⭐ 减少了首次加载的 bundle 大小
```

### 1.3 ErrorBoundary：捕获渲染错误

```tsx
// ErrorBoundary 是 React 里唯一还需要 class 组件的地方（截至 React 19）
// 实际项目中用 react-error-boundary 库

import { ErrorBoundary } from 'react-error-boundary'

function App() {
  return (
    <ErrorBoundary
      fallback={<div>页面出错了，请刷新</div>}
      onError={(error) => console.error('捕获到错误:', error)}
    >
      <MyApp />
    </ErrorBoundary>
  )
}

// ⭐ Suspense 处理"还没准备好"
// ErrorBoundary 处理"出错了"
// 两者经常一起用：

<ErrorBoundary fallback={<ErrorPage />}>
  <Suspense fallback={<Spinner />}>
    <Dashboard />
  </Suspense>
</ErrorBoundary>
```

---

## 2. React 19 新特性

### 2.1 use() Hook

```tsx
import { use, Suspense } from 'react'

// use() 可以在组件内直接读取 Promise 的值
function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  const user = use(userPromise)   // ⭐ 直接读取，不需要 .then()!
  // 如果 Promise 还在 pending → use 会"挂起"组件 → Suspense 显示 fallback
  // 如果 Promise resolve 了 → user 就是结果值
  // 如果 Promise reject 了 → 向上冒泡到 ErrorBoundary

  return <div>{user.name}</div>
}

// 使用
function App() {
  const userPromise = fetchUser(1)  // 注意：在组件外创建 Promise

  return (
    <Suspense fallback={<Spinner />}>
      <UserProfile userPromise={userPromise} />
    </Suspense>
  )
}

// ⭐ use() 和 await 的区别：
// await：暂停整个函数
// use()：暂停该组件的渲染，显示最近的 Suspense fallback，其他组件不受影响

// ⭐ use() 还能读取 Context（取代 useContext）
const theme = use(ThemeContext)

// ⭐ use() 不受 Hooks 规则限制
// 可以在 if/for 里调用（因为它不是传统意义上的 Hook）
```

### 2.2 useActionState（原 useFormState）

```tsx
import { useActionState } from 'react'

function LoginForm() {
  const [state, formAction, isPending] = useActionState(
    async (prevState: any, formData: FormData) => {
      const email = formData.get('email') as string
      const password = formData.get('password') as string

      try {
        await login(email, password)
        return { success: true, error: null }
      } catch (e) {
        return { success: false, error: '登录失败' }
      }
    },
    { success: false, error: null }   // 初始状态
  )

  return (
    <form action={formAction}>
      <input name="email" type="email" />
      <input name="password" type="password" />
      <button disabled={isPending}>
        {isPending ? '登录中...' : '登录'}
      </button>
      {state.error && <p className="error">{state.error}</p>}
    </form>
  )
}

// ⭐ 不需要 useState + onSubmit + e.preventDefault + try/catch
// React 19 让表单处理大幅简化
```

### 2.3 useOptimistic

```tsx
import { useOptimistic } from 'react'

function TodoList({ todos }: { todos: Todo[] }) {
  const [optimisticTodos, addOptimistic] = useOptimistic(
    todos,
    (currentTodos, newTodoText: string) => [
      ...currentTodos,
      { id: Date.now(), text: newTodoText, done: false, pending: true }
    ]
  )

  const handleAdd = async (text: string) => {
    addOptimistic(text)             // 立即在 UI 上显示
    await fetch('/api/todos', {     // 同时发请求
      method: 'POST',
      body: JSON.stringify({ text })
    })
    // 请求完成后，React 自动用真实数据替换乐观数据
  }

  return (
    <ul>
      {optimisticTodos.map(todo => (
        <li key={todo.id} style={{ opacity: todo.pending ? 0.5 : 1 }}>
          {todo.text}
        </li>
      ))}
    </ul>
  )
}

// ⭐ 乐观更新：操作后立刻在 UI 上反馈，不等后端响应
// 如果请求失败，React 会自动回退到之前的状态
```

---

## 3. Server Components 简介

### 3.1 什么是 Server Components

```
传统 React（Client Components）：
  → 所有组件在浏览器里运行
  → 数据请求：浏览器 → API → 浏览器
  → 需要发送所有组件的 JS 代码到浏览器

Server Components（RSC）：
  → 部分组件在服务器上运行
  → 数据请求：服务器 → 数据库（同一网络，更快）
  → 服务器组件的 JS 不需要发送到浏览器

    ┌─────────────────────────────────────┐
    │ 服务器                              │
    │  ┌─────────────┐                    │
    │  │Server Comp  │ → 直接查数据库     │
    │  │（不发到浏览器）│ → 渲染成 HTML     │
    │  └─────────────┘                    │
    │         ↓ 只传渲染结果（不传 JS）      │
    └─────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────┐
    │ 浏览器                              │
    │  ┌─────────────┐                    │
    │  │Client Comp  │ → 有交互、有状态   │
    │  │（有 JS 代码）│ → useState/onClick │
    │  └─────────────┘                    │
    └─────────────────────────────────────┘
```

### 3.2 Server vs Client Component

```
Server Component：
  ✅ 直接访问数据库/文件系统
  ✅ JS 不发送到浏览器（减少 bundle 大小）
  ✅ 可以 async/await
  ❌ 不能用 useState/useEffect（没有生命周期）
  ❌ 不能用事件处理（onClick 等）
  ❌ 不能用浏览器 API（DOM, localStorage...）

Client Component：
  ✅ 可以用 useState/useEffect
  ✅ 可以处理用户交互
  ✅ 可以用浏览器 API
  ❌ 不能直接访问服务器资源

  → 需要交互 → Client Component（加 'use client' 指令）
  → 纯展示/数据获取 → Server Component
```

### 3.3 要不要现在学？

```
⭐ 建议：了解概念即可，不用深入

原因：
  → Server Components 需要框架支持（Next.js / Remix）
  → 对于客户端渲染的 SPA（你目前在做的），不需要 RSC
  → 掌握前 7 个阶段的内容 >>> 学 RSC

何时深入学习：
  → 当你开始用 Next.js 做项目时
  → 当你需要 SEO 或首屏性能优化时
  → 当团队决定迁移到 Next.js 时
```

---

## 4. 元框架：Next.js

### 4.1 什么是元框架

```
React 本身只是一个 UI 库，不包含：
  → 文件路由
  → 服务端渲染 (SSR)
  → 静态生成 (SSG)
  → API 路由
  → 构建优化

元框架 = React + 上述所有能力：
  Next.js：最主流的 React 元框架（Vercel 维护）
  Remix：另一个选择（React Router 团队）

何时用元框架：
  ✅ 需要 SEO（落地页、博客、电商）
  ✅ 需要首屏性能（服务端渲染）
  ✅ 全栈开发（API Routes）
  ❌ 纯后台管理系统 → Vite + React 就够了
```

---

## 5. 生态速览

### 5.1 必备工具

```
工具库速查（按使用频率排序）：

  状态管理      → Zustand（全局 UI）+ TanStack Query（服务端数据）
  路由         → React Router（SPA）/ Next.js 文件路由（全栈）
  样式         → CSS Modules / Tailwind CSS / styled-components
  表单         → React Hook Form + Zod（表单管理 + 校验）
  UI 组件库    → Shadcn/ui（推荐）/ Ant Design / MUI
  构建工具     → Vite（SPA）/ Next.js（全栈）
  测试         → Vitest + React Testing Library
  代码质量     → ESLint + Prettier

  ⚠️ 不需要一次学完！按项目需求逐步引入
```

---

## 6. 练习：实战项目

### 6.1 项目 1：Todo App Pro（巩固阶段 1-5）

```
功能：
  ✅ 增删改查 + 标记完成
  ✅ 筛选（全部/已完成/未完成）
  ✅ 本地存储持久化（useLocalStorage）
  ✅ 主题切换（dark/light） 
  ✅ TypeScript 全程使用

技术栈：
  Vite + React + TypeScript
  useState / useReducer / useContext / useRef / useEffect
  自定义 Hook（useTodos, useLocalStorage, useTheme）
  React.memo + useCallback 优化列表渲染

检验标准：
  → 能脱离文档独立完成
  → 代码结构清晰（逻辑/UI 分离）
  → DevTools Profiler 无不必要渲染
```

### 6.2 项目 2：个人仪表盘（巩固阶段 6-7）

```
功能：
  ✅ 多页面路由（首页/用户管理/设置）
  ✅ 用户列表 + 详情页（TanStack Query + jsonplaceholder API）
  ✅ CRUD 操作（useMutation + invalidateQueries）
  ✅ 全局状态（Zustand：侧边栏/主题/通知）
  ✅ 路由守卫（模拟登录状态）

技术栈：
  Vite + React + TypeScript
  React Router（嵌套路由 + 动态路由）
  TanStack Query（数据请求 + 缓存）
  Zustand（全局 UI 状态 + 持久化）

检验标准：
  → 流畅的多页面导航体验
  → 数据请求有 loading/error 状态
  → 状态管理层次清晰（local/server/global）
```

### 6.3 项目 3：协作看板（综合全部 + React 19）

```
功能：
  ✅ 看板列表（类似 Trello）
  ✅ 拖拽排序（可用 @dnd-kit/core）
  ✅ 实时协作（可用 WebSocket 模拟）
  ✅ 乐观更新（useOptimistic）
  ✅ 代码分割（React.lazy + Suspense）
  ✅ 错误边界（react-error-boundary）

技术栈：
  全部前述技术 + React 19 新特性
  可选：Shadcn/ui 组件库

检验标准：
  → 拖拽操作流畅
  → 乐观更新体验自然
  → 错误和加载状态处理完善
  → 代码可维护性高
```

---

## 7. 面试常问

### Q1: Suspense 是什么？解决什么问题？

**答**：
- Suspense 是一个组件边界，声明"在子组件还没准备好时显示 fallback"
- 解决的问题：统一的加载状态处理——不用每个组件自己管 loading 状态
- 两个主要用途：
  1. 代码分割：配合 `React.lazy` 在加载组件代码时显示 loading
  2. 数据请求：配合 `use()` 或 TanStack Query suspense 模式
- 不是自己发请求，只是一个"等待边界"

### Q2: React 19 的 use() 和 useEffect 请求数据有什么区别？

**答**：
- `useEffect`：组件先渲染（显示 loading）→ 请求数据 → 更新 state → 再次渲染
- `use()`：如果 Promise 未完成 → 组件"挂起" → Suspense 显示 fallback → Promise 完成 → 组件渲染
- `use()` 让数据请求和 Suspense 配合，更声明式；`useEffect` 需要手动管理 loading/error 状态
- `use()` 可以在条件语句中调用，不受 Hooks 规则限制

### Q3: Server Components 和 Client Components 的区别？

**答**：
- Server Components 在服务端运行，可以直接访问数据库，JS 代码不发送到浏览器，但不能有交互
- Client Components 在浏览器运行，可以用 useState/useEffect/事件处理，但需要发送 JS 到浏览器
- 默认是 Server Component（在 Next.js 的 App Router 中），加 `'use client'` 变成 Client Component
- 实际应用：静态展示用 Server Component，交互用 Client Component

### Q4: 什么时候用 Next.js，什么时候用 Vite？

**答**：
- **Vite + React**：纯客户端 SPA，如后台管理系统、工具类应用、不需要 SEO 的应用
- **Next.js**：需要 SEO（落地页、博客、电商）、需要 SSR/SSG、全栈开发、需要 Server Components
- 对于学习 React 基础和大多数企业后台项目，Vite 就够了

---

## 📖 持续学习资源

```
官方文档：
  → react.dev — 最权威的 React 文档
  → nextjs.org — Next.js 文档

深度文章：
  → overreacted.io — Dan Abramov 的博客（核心概念深度解析）
  → kentcdodds.com — Kent C. Dodds 的文章（实战模式）
  → tkdodo.eu — TanStack Query 维护者的博客

视频：
  → Theo Browne（t3.gg）— 现代 React 生态评测
  → Jack Herrington — React 高级模式

中文资源：
  → react.docschina.org — React 中文文档
  → 掘金/知乎 React 专栏

⭐ 最好的学习资源永远是：打开编辑器，开始写代码
```

> ⬅️ [上一阶段：状态管理 + 性能优化](./07-state-performance.md) | 🎉 [返回路线概览](../react-learning-roadmap.md)
