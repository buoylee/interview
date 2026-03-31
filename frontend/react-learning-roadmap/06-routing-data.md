# 阶段 6：路由 + 数据层（1-2 天）

> **一句话定位**：单个组件设计搞定了，现在学如何把多个组件组织成完整的多页面应用，以及如何优雅地与后端 API 交互。

---

## 目录

- [1. React Router 基础](#1-react-router-基础)
- [2. 路由进阶](#2-路由进阶)
- [3. TanStack Query 基础](#3-tanstack-query-基础)
- [4. TanStack Query 进阶](#4-tanstack-query-进阶)
- [5. 路由 + 数据层整合](#5-路由--数据层整合)
- [6. 面试常问](#6-面试常问)
- [7. 练习](#7-练习)

---

## 1. React Router 基础

### 1.1 为什么需要路由

```
SPA（单页应用）的问题：
  → 只有一个 HTML 页面
  → 用 JS 动态切换内容
  → 但 URL 不变 → 用户无法收藏/分享/后退

路由解决方案：
  → URL 变化时显示不同组件
  → 不刷新页面（客户端路由）
  → 支持前进/后退/收藏
```

### 1.2 安装与基本配置

```bash
npm install react-router-dom
```

```tsx
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'

function App() {
  return (
    <BrowserRouter>
      {/* 导航 */}
      <nav>
        <Link to="/">首页</Link>          {/* Link 替代 <a>，不会整页刷新 */}
        <Link to="/users">用户</Link>
        <Link to="/about">关于</Link>
      </nav>

      {/* 路由规则 */}
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/users" element={<UserList />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<NotFound />} />   {/* 404 兜底 */}
      </Routes>
    </BrowserRouter>
  )
}
```

### 1.3 和 Vue Router 的对比

```
                    React Router              Vue Router
配置方式            JSX 声明式                  对象配置式
组件占位            <Routes>+<Route>           <RouterView />
导航链接            <Link to="...">            <RouterLink to="...">
嵌套路由            <Route> 嵌套 + <Outlet>    children 数组 + <RouterView>
获取参数            useParams()                useRoute().params
编程导航            useNavigate()              useRouter().push()
路由守卫            loader / 直接在组件里判断    beforeEach / beforeEnter

核心区别：
  Vue Router 是"集中配置"（一个 routes 数组定义所有路由）
  React Router 是"组件式"（路由规则就是 JSX，可以像组件一样组合）
```

---

## 2. 路由进阶

### 2.1 动态路由与参数

```tsx
import { useParams } from 'react-router-dom'

// 路由配置
<Route path="/users/:id" element={<UserDetail />} />               {/* :id = 动态参数 */}
<Route path="/posts/:category/:postId" element={<PostDetail />} /> {/* 多个参数 */}

// 组件中获取参数
function UserDetail() {
  const { id } = useParams()   // id 的类型是 string | undefined
  // URL /users/42 → id = "42"

  return <div>用户 ID: {id}</div>
}
```

### 2.2 嵌套路由 + Outlet

```tsx
import { Outlet } from 'react-router-dom'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>           {/* 父路由：布局 */}
          <Route index element={<Home />} />             {/* index = 默认子路由 */}
          <Route path="users" element={<UserList />} />
          <Route path="users/:id" element={<UserDetail />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

// Layout 组件：提供公共布局（导航栏、侧边栏...）
function Layout() {
  return (
    <div>
      <nav>
        <Link to="/">首页</Link>
        <Link to="/users">用户</Link>
        <Link to="/settings">设置</Link>
      </nav>
      <main>
        <Outlet />    {/* ⭐ 子路由的内容渲染在这里 */}
      </main>          {/* ≈ Vue 的 <RouterView /> */}
    </div>
  )
}
```

### 2.3 编程式导航

```tsx
import { useNavigate, useLocation } from 'react-router-dom'

function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogin = async () => {
    await login(credentials)

    // 编程式导航
    navigate('/dashboard')              // 跳转
    navigate(-1)                         // 后退
    navigate('/users', { replace: true }) // 替换当前历史记录（不能后退回来）
    navigate('/dashboard', { state: { from: location.pathname } })  // 传状态
  }

  return (/* ... */)
}
```

### 2.4 路由守卫（受保护路由）

```tsx
// React Router 没有 Vue 的 beforeEach，但可以用组件模式实现

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()       // 自定义 Hook 获取认证状态
  const location = useLocation()

  if (!user) {
    // 未登录 → 重定向到登录页，记住当前位置
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

// 使用：包裹需要保护的路由
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route path="/dashboard" element={
    <ProtectedRoute>
      <Dashboard />
    </ProtectedRoute>
  } />
</Routes>
```

---

## 3. TanStack Query 基础

### 3.1 为什么不用 useEffect + fetch

```
用 useEffect + fetch 管理数据请求有什么问题？

  你需要手动处理：
    ✅ loading / error / success 状态     → 每个请求都写一遍
    ✅ 竞态条件                           → cancelled 标记
    ✅ 缓存                              → 完全没有
    ✅ 重复请求去重                        → 完全没有
    ✅ 后台刷新                           → 自己写
    ✅ 错误重试                           → 自己写
    ✅ 分页和无限滚动                     → 自己写

TanStack Query 一行搞定上面所有问题：
  const { data, isLoading, error } = useQuery({ queryKey, queryFn })

和 Vue Query 是同一个库！
  → @tanstack/react-query（React 版）
  → @tanstack/vue-query（Vue 版）
  → API 几乎一样，概念完全相通
```

### 3.2 安装与配置

```bash
npm install @tanstack/react-query
```

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>   {/* 类似 Vue 的 provide */}
      <MyApp />
    </QueryClientProvider>
  )
}
```

### 3.3 useQuery：读取数据

```tsx
import { useQuery } from '@tanstack/react-query'

function UserList() {
  const {
    data: users,        // 返回的数据（类型自动推断）
    isLoading,          // 首次加载中
    error,              // 错误信息
    isError,            // 是否出错
    refetch,            // 手动重新请求
    isFetching,         // 是否在请求中（包括后台刷新）
  } = useQuery({
    queryKey: ['users'],                                      // ⭐ 缓存键
    queryFn: () => fetch('/api/users').then(r => r.json()),    // 请求函数
    staleTime: 5 * 60 * 1000,                                 // 5 分钟内认为数据是新鲜的
  })

  if (isLoading) return <Spinner />
  if (isError) return <p>错误：{error.message}</p>
  return (
    <ul>
      {users.map((u: User) => <li key={u.id}>{u.name}</li>)}
    </ul>
  )
}
```

### 3.4 queryKey：缓存的核心

```tsx
// queryKey 决定了缓存的身份——相同 key 共享缓存

// 整个用户列表
useQuery({ queryKey: ['users'], queryFn: fetchUsers })

// 特定用户（key 包含参数）
useQuery({ queryKey: ['users', userId], queryFn: () => fetchUser(userId) })

// 带筛选条件
useQuery({ queryKey: ['users', { role: 'admin', page: 1 }], queryFn: ... })

// ⭐ key 的规则：
// 1. 包含的参数不同 → 视为不同的查询 → 独立缓存
// 2. 数组里的值用 Object.is() 对比
// 3. 约定：第一个元素是"实体名"，后续是参数
//    ['users'] → 用户列表
//    ['users', 1] → id=1 的用户
//    ['users', { page: 2 }] → 用户列表第 2 页
```

---

## 4. TanStack Query 进阶

### 4.1 useMutation：写数据

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'

function CreateUserForm() {
  const queryClient = useQueryClient()

  const createUser = useMutation({
    // 请求函数
    mutationFn: (newUser: Omit<User, 'id'>) =>
      fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newUser)
      }).then(r => r.json()),

    // 成功后刷新用户列表缓存
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      // ⭐ invalidate = 标记缓存过期 → 自动重新请求
    },

    onError: (error) => {
      alert('创建失败：' + error.message)
    }
  })

  const handleSubmit = (formData: { name: string; email: string }) => {
    createUser.mutate(formData)
    //         ↑ 触发 mutation
  }

  return (
    <form onSubmit={/* ... */}>
      {/* ... */}
      <button disabled={createUser.isPending}>
        {createUser.isPending ? '创建中...' : '创建用户'}
      </button>
    </form>
  )
}
```

### 4.2 缓存与后台刷新

```
TanStack Query 的缓存策略：

  staleTime（新鲜时间）：
    → 数据在这段时间内被认为是"新鲜的"
    → 新鲜数据不会重新请求
    → 默认 0（每次都重新请求）
    → 推荐按业务设置：5分钟用户列表、1小时配置数据...

  gcTime（垃圾回收时间，旧名 cacheTime）：
    → 数据不再被任何组件使用后，保留缓存多久
    → 默认 5 分钟
    → 在这段时间内重新访问页面 → 立即显示缓存数据 + 后台刷新

  常见场景：
    组件 A 请求 ['users'] → 数据缓存
    切到其他页面 → 组件 A 卸载
    切回来 → 组件 A 重新挂载 → 立即显示缓存 + 后台重新请求
    → 用户看到的是"旧数据秒开 + 新数据无缝更新"
```

### 4.3 useQuery 的 enabled 选项

```tsx
// 场景：先选用户，再加载用户的订单
function UserOrders() {
  const [userId, setUserId] = useState<number | null>(null)

  const { data: orders } = useQuery({
    queryKey: ['orders', userId],
    queryFn: () => fetchOrders(userId!),
    enabled: userId !== null,     // ⭐ 只有选了用户才发请求
  })

  return (/* ... */)
}
```

---

## 5. 路由 + 数据层整合

### 5.1 典型的页面结构

```tsx
// 一个完整的"用户管理"页面结构

// App.tsx — 路由配置
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="users" element={<UserList />} />
            <Route path="users/:id" element={<UserDetail />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

// UserList.tsx — 列表页
function UserList() {
  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers
  })
  const navigate = useNavigate()

  if (isLoading) return <Spinner />
  return (
    <ul>
      {users?.map(user => (
        <li key={user.id} onClick={() => navigate(`/users/${user.id}`)}>
          {user.name}
        </li>
      ))}
    </ul>
  )
}

// UserDetail.tsx — 详情页
function UserDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const { data: user, isLoading } = useQuery({
    queryKey: ['users', id],
    queryFn: () => fetchUser(Number(id)),
    enabled: !!id
  })

  if (isLoading) return <Spinner />
  return (
    <div>
      <button onClick={() => navigate('/users')}>← 返回列表</button>
      <h1>{user?.name}</h1>
      <p>{user?.email}</p>
    </div>
  )
}
```

---

## 6. 面试常问

### Q1: React Router 和 Vue Router 核心区别？

**答**：
- React Router 是组件式配置（路由就是 JSX），Vue Router 是对象式配置（routes 数组）
- React Router 没有内置路由守卫（通过组件模式 `<ProtectedRoute>` 实现），Vue Router 有 `beforeEach`
- 嵌套路由：React 用 `<Outlet>`，Vue 用 `<RouterView>`
- 核心思想一致：URL 变化 → 渲染对应组件，支持动态参数、嵌套路由、编程导航

### Q2: TanStack Query 比 useEffect + fetch 好在哪？

**答**：
- **自动缓存**：相同 queryKey 的请求会复用缓存，多个组件请求同一数据只发一次
- **后台刷新**：切换页面再回来，立即显示缓存 + 后台重新请求 → 用户体验好
- **标准化**：loading/error/success 状态、错误重试、请求取消都内置处理
- **声明式**：你只描述"要什么数据"，不用手动管理请求生命周期
- 和 Vue Query 是同一个库，概念完全相通

### Q3: queryKey 的作用是什么？

**答**：
- queryKey 是缓存的唯一标识。相同 key 共享缓存，不同 key 独立缓存
- 包含的参数变化时（如 `['users', userId]` 中 `userId` 变了），自动触发新请求
- 通过 `invalidateQueries({ queryKey: ['users'] })`，可以标记缓存过期触发刷新

---

## 7. 练习

```
路由：
  1. 用 React Router 搭一个 3 页面 SPA（首页 + 用户列表 + 用户详情）
     → 嵌套路由 + Layout（公共导航栏）
     → 动态路由 /users/:id
     → 404 页面

  2. 实现一个 ProtectedRoute
     → 用 useState 模拟登录状态
     → 未登录访问 /dashboard → 重定向到 /login

数据层：
  3. 用 TanStack Query + jsonplaceholder API 实现：
     → 用户列表（/users）
     → 点击用户 → 跳转到用户详情页（/users/:id）
     → 详情页展示用户信息 + 用户的 posts 列表

  4. 实现"创建用户"功能（useMutation）
     → 成功后自动刷新用户列表

综合：
  5. 把练习 3-4 和阶段 5 的 PageLayout 组件结合
     → 完整的多页面应用：布局 + 路由 + 数据请求
```

---

## 📖 推荐学习路径

1. [React Router 官方教程](https://reactrouter.com/en/main/start/tutorial) — 跟着做一遍
2. [TanStack Query 官方文档](https://tanstack.com/query/latest/docs/react/overview) — 重点看 Quick Start 和 Guides
3. 核心：亲手搭一个"列表 + 详情"的完整 CRUD 应用

> ⬅️ [上一阶段：组件设计 & 复用模式](./05-component-patterns.md) | ➡️ [下一阶段：状态管理 + 性能优化](./07-state-performance.md)
