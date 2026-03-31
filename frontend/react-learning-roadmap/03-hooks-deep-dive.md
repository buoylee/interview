# 阶段 3：Hooks 深度理解（2-3 天）⭐ 最核心

> **一句话定位**：Hooks 是现代 React 的全部。理解了 Hooks 的执行时机和心智模型，你就掌握了 React 的核心能力。

---

## 目录

- [1. Hooks 是什么 & 为什么](#1-hooks-是什么--为什么)
- [2. 组件生命周期全景](#2-组件生命周期全景)
- [3. useEffect：副作用处理](#3-useeffect副作用处理)
- [4. 闭包陷阱](#4-闭包陷阱)
- [5. useRef：可变值 + DOM 访问](#5-useref可变值--dom-访问)
- [6. useContext：跨层级传数据](#6-usecontext跨层级传数据)
- [7. useReducer：复杂状态逻辑](#7-usereducer复杂状态逻辑)
- [8. Hooks 规则](#8-hooks-规则)
- [9. Hooks 选择决策树](#9-hooks-选择决策树)
- [10. 面试常问](#10-面试常问)
- [11. 练习](#11-练习)

---

## 1. Hooks 是什么 & 为什么

### 1.1 一句话理解

```
Hooks = 让函数组件拥有"状态"和"副作用"能力的函数

  在 Hooks 之前：
    函数组件是"无状态"的，只能做纯展示
    需要状态/生命周期 → 必须用 class 组件

  有了 Hooks 之后：
    函数组件能做 class 组件能做的一切
    → class 组件基本退出历史

  为什么函数组件 + Hooks 更好？
    ✅ 更简洁（没有 this、没有 constructor、没有 bind）
    ✅ 逻辑可复用（自定义 Hook，阶段 5 详讲）
    ✅ 更容易理解（每次渲染就是一次函数调用）
```

### 1.2 内置 Hooks 全家福

```
本阶段覆盖（核心 5 个）：
  useState    → 阶段 2 已学，本阶段不重复
  useEffect   → 副作用处理（最容易出错）
  useRef      → 可变值 + DOM 访问
  useContext   → 跨层级传数据
  useReducer   → 复杂状态逻辑

阶段 7 覆盖（性能优化 3 个）：
  useMemo     → 缓存计算结果
  useCallback → 缓存函数引用
  memo()      → 缓存组件渲染（不是 Hook，但紧密相关）

阶段 8 覆盖（React 19 新增）：
  use         → 异步数据读取
  useActionState → 表单异步操作
  useOptimistic  → 乐观更新
```

---

## 2. 组件生命周期全景

### 2.1 函数组件的"生命周期"

```
虽然函数组件没有 class 组件的 lifecycle 方法（componentDidMount 等），
但依然有生命周期概念。理解它是理解所有 Hook 执行时机的前提：

  ┌──────────────────────────────────────────────────┐
  │                                                  │
  │   挂载（Mount）                                   │
  │     ↓                                            │
  │   ① 组件函数执行（Render Phase）                   │
  │     → useState 返回初始值                          │
  │     → 计算 JSX                                    │
  │     ↓                                            │
  │   ② DOM 更新（Commit Phase）                       │
  │     → React 把 JSX 变成真实 DOM                    │
  │     ↓                                            │
  │   ③ useEffect 回调执行                             │
  │     → DOM 已经在页面上了                            │
  │     → 现在可以安全地做副作用（请求、订阅...）          │
  │                                                  │
  │   ┌──── 更新循环（state/props 变化时）─────┐       │
  │   ↓                                      │       │
  │   ① 组件函数重新执行                       │       │
  │     → useState 返回最新值（不是初始值）      │       │
  │     → 计算新 JSX                          │       │
  │     ↓                                    │       │
  │   ② DOM 更新（diff 后只更新变化部分）        │       │
  │     ↓                                    │       │
  │   ③ 旧 effect 的清理函数执行               │       │
  │     ↓                                    │       │
  │   ④ 新 effect 回调执行                    │       │
  │     └────────────────────────────────────┘       │
  │                                                  │
  │   卸载（Unmount）                                  │
  │     → 最后一次 effect 清理函数执行                   │
  │     → 组件从 DOM 中移除                             │
  │                                                  │
  └──────────────────────────────────────────────────┘
```

### 2.2 和 Vue 生命周期的对应 ⭐

```
Vue                          React（函数组件 + Hooks）
───────────────              ─────────────────────────
beforeCreate / created       组件函数体执行（本身就是"创建"）
onMounted                    useEffect(() => {...}, [])
onUpdated                    useEffect(() => {...})（无依赖，每次渲染后）
onBeforeUnmount              useEffect 的 return () => {...}
watch(source, cb)            useEffect(() => {...}, [source])
computed                     直接在函数体里计算 / useMemo

关键区别：
  Vue: 生命周期是"事件" → 某个时刻触发一个回调
  React: Hook 是"声明" → 描述副作用和它的依赖，React 决定何时执行
```

---

## 3. useEffect：副作用处理

### 3.1 什么是"副作用"

```
组件的主要工作是：接收 props/state → 返回 JSX
这个过程应该是"纯"的（同样的输入 → 同样的输出）

"副作用"是指和外部世界的交互，不属于"计算 UI"的事情：
  ✅ 数据请求（fetch API）
  ✅ 订阅（WebSocket、事件监听）
  ✅ 操作 DOM（设置 title、滚动位置...）
  ✅ 定时器（setTimeout、setInterval）
  ✅ 日志记录

这些事情不能直接写在组件函数体里，因为：
  → 组件函数在"渲染阶段"执行，此时 DOM 可能还没更新
  → 副作用应该在 DOM 更新之后执行
  → useEffect 就是告诉 React："DOM 更新后帮我执行这个"
```

### 3.2 基本语法

```jsx
useEffect(() => {
  // Effect 回调：DOM 更新后执行
  
  return () => {
    // 清理函数（可选）：下次 effect 执行前 或 组件卸载时执行
  }
}, [依赖1, 依赖2])  // 依赖数组（可选）
```

### 3.3 三种依赖模式

```jsx
// ① 无依赖数组 → 每次渲染后都执行（几乎不用）
useEffect(() => {
  console.log('每次渲染后都执行')
})

// ② 空依赖数组 → 仅挂载时执行一次
useEffect(() => {
  console.log('只在组件挂载时执行一次')
  // ≈ Vue 的 onMounted
  
  return () => {
    console.log('组件卸载时执行')
    // ≈ Vue 的 onBeforeUnmount
  }
}, [])

// ③ 有依赖数组 → 依赖变化时执行
useEffect(() => {
  console.log(`userId 变成了 ${userId}`)
  // ≈ Vue 的 watch(userId, callback)
  
  return () => {
    console.log(`清理 userId=${userId} 的副作用`)
  }
}, [userId])
```

### 3.4 实战：数据请求

```jsx
function UserProfile({ userId }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // ⭐ 竞态处理：防止旧请求覆盖新请求的结果
    let cancelled = false
    
    setLoading(true)
    setError(null)

    fetch(`/api/users/${userId}`)
      .then(res => {
        if (!res.ok) throw new Error('请求失败')
        return res.json()
      })
      .then(data => {
        if (!cancelled) {    // 只有未取消时才更新
          setUser(data)
          setLoading(false)
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      })

    return () => {
      cancelled = true     // 依赖变化或卸载时取消
    }
  }, [userId])

  if (loading) return <div>加载中...</div>
  if (error) return <div>错误: {error}</div>
  return <div>{user.name}</div>
}

// 为什么需要竞态处理？
// 用户快速切换 userId: 1 → 2 → 3
// 如果请求 1 比请求 3 晚返回，不处理竞态就会显示 user 1 的数据
// cancelled 标记确保只有最新请求的结果被使用
```

### 3.5 实战：事件监听

```jsx
function WindowSize() {
  const [size, setSize] = useState({ w: window.innerWidth, h: window.innerHeight })

  useEffect(() => {
    const handleResize = () => {
      setSize({ w: window.innerWidth, h: window.innerHeight })
    }

    window.addEventListener('resize', handleResize)

    // ⭐ 清理：移除监听器，防止内存泄漏
    return () => window.removeEventListener('resize', handleResize)
  }, [])  // 空依赖：只在挂载时添加监听，卸载时移除

  return <p>窗口大小: {size.w} × {size.h}</p>
}
```

### 3.6 实战：定时器

```jsx
function Timer() {
  const [seconds, setSeconds] = useState(0)
  const [isRunning, setIsRunning] = useState(false)

  useEffect(() => {
    if (!isRunning) return   // 未运行时不设定时器

    const timer = setInterval(() => {
      setSeconds(prev => prev + 1)   // ⭐ 必须用函数式更新！
    }, 1000)

    return () => clearInterval(timer)  // ⭐ 清理定时器
  }, [isRunning])  // isRunning 变化时重新设置/清除定时器

  return (
    <div>
      <p>{seconds} 秒</p>
      <button onClick={() => setIsRunning(!isRunning)}>
        {isRunning ? '暂停' : '开始'}
      </button>
      <button onClick={() => { setIsRunning(false); setSeconds(0) }}>重置</button>
    </div>
  )
}
```

### 3.7 useEffect 不是 Vue 的 watch

```
这是从 Vue 转 React 最容易犯的概念错误：

  ❌ 把 useEffect 当 watch 用：
  useEffect(() => {
    setFullName(firstName + ' ' + lastName)   // 错！这不是副作用
  }, [firstName, lastName])

  ✅ 直接在函数体里计算（它就是一个 JS 函数！）：
  const fullName = firstName + ' ' + lastName

  useEffect 应该用于什么？
    → 和"外部世界"同步：API 请求、DOM 操作、订阅、日志...
    → 不应该用于：从 state 计算新 state

  判断标准：
    "这行代码去掉，UI 会错吗？" → 如果会错，说明它是渲染逻辑，不该放 useEffect
    "这行代码去掉，外部行为会错吗？" → 如果会错，才该放 useEffect
```

### 3.8 useEffect 常见错误总结

```
错误 1：依赖数组漏写
  useEffect(() => {
    fetchUser(userId)     // 用了 userId
  }, [])                  // ❌ 依赖没写 userId → userId 变了但 effect 不重新执行

  ✅ useEffect(() => { fetchUser(userId) }, [userId])

错误 2：对象/数组做依赖
  useEffect(() => {
    // ...
  }, [{ key: 'value' }])
  // ❌ 每次渲染都创建新对象 → 引用不同 → effect 无限执行

  ✅ 依赖基本类型值，或用 useMemo 缓存对象

错误 3：忘记清理
  useEffect(() => {
    const timer = setInterval(() => ..., 1000)
    // ❌ 没有 return 清理 → 每次渲染都加一个新定时器 → 内存泄漏
  }, [])

  ✅ return () => clearInterval(timer)

错误 4：在 effect 里 setState 导致无限循环
  useEffect(() => {
    setData(transformData(props.raw))  // setState → 触发渲染 → 触发 effect → setState...
  })  // ❌ 无依赖 = 每次渲染都执行

  ✅ 直接在函数体里计算：const data = transformData(props.raw)
```

---

## 4. 闭包陷阱

### 4.1 什么是闭包陷阱

```
闭包陷阱是 React Hooks 最经典的 bug，必须深刻理解。

根本原因：
  → 组件每次渲染 = 一次新的函数调用
  → 该次调用中的所有变量（state, props, 函数）都是那次渲染的"快照"
  → useEffect/事件处理函数 "记住" 了创建时的变量值
  → 如果 effect 不重新执行，它拿到的永远是旧快照里的值
```

### 4.2 经典示例：定时器里的过期值

```jsx
function Counter() {
  const [count, setCount] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      console.log(count)    // ⚠️ 永远打印 0！
    }, 1000)
    return () => clearInterval(timer)
  }, [])  // 空依赖 → effect 只在挂载时执行一次

  return <button onClick={() => setCount(c => c + 1)}>{count}</button>
}

// 发生了什么？
//
// 第 1 次渲染：count = 0
//   → useEffect 执行，创建 setInterval
//   → setInterval 的回调函数"捕获"了 count = 0（闭包）
//   → 这个回调永远用的是 count = 0
//
// 第 2 次渲染：count = 1
//   → 但 setInterval 的回调不会更新！
//   → 因为 effect 的依赖是 []，不会重新执行
//   → 旧回调还是闭包着第 1 次渲染的 count = 0
```

### 4.3 修复方式

```jsx
// ————— 修复方式 1：把依赖加进数组 —————
useEffect(() => {
  const timer = setInterval(() => {
    console.log(count)   // ✅ 现在每次 count 变化都重建定时器
  }, 1000)
  return () => clearInterval(timer)
}, [count])  // count 变了 → 清除旧定时器 → 创建新定时器
// ⚠️ 代价：定时器频繁销毁重建（对定时器可能不太适合）


// ————— 修复方式 2：用 ref 保存最新值 —————
const countRef = useRef(count)
countRef.current = count       // 每次渲染都同步到 ref

useEffect(() => {
  const timer = setInterval(() => {
    console.log(countRef.current)  // ✅ ref.current 永远是最新值
  }, 1000)
  return () => clearInterval(timer)
}, [])  // 定时器只创建一次
// 因为 ref 是一个可变容器（{ current: ... }）
// 闭包捕获的是 ref 对象本身（引用不变），但 .current 可以随时更新


// ————— 修复方式 3：用函数式 setState —————
useEffect(() => {
  const timer = setInterval(() => {
    setCount(prev => prev + 1)  // ✅ 不依赖闭包里的 count
    // prev 是 React 内部提供的最新值
  }, 1000)
  return () => clearInterval(timer)
}, [])
// 如果你只需要基于旧值更新 state，这是最简洁的方式
// 但如果你需要读取 count 做其他事情（不只是更新），还是要用 ref
```

### 4.4 闭包陷阱的通用规律

```
什么时候会遇到闭包陷阱？

  ✅ 会遇到的情况：
    → useEffect 依赖数组是 []（只执行一次），但回调中用了 state
    → setTimeout/setInterval 的回调中用了 state
    → addEventListener 的回调中用了 state

  ❌ 不会遇到的情况：
    → 普通的 onClick 事件处理（每次渲染都绑新函数，自然拿到最新值）
    → useEffect 的依赖数组里包含了用到的所有 state

  预防手段：
    1. 依赖数组写完整（ESLint 的 exhaustive-deps 规则会帮你检查）
    2. 需要在"只执行一次"的 effect 里用最新 state → 用 useRef
    3. 只是基于旧 state 计算新 state → 用函数式更新 setState(prev => ...)
```

---

## 5. useRef：可变值 + DOM 访问

### 5.1 useRef 的本质

```
useRef 返回一个"可变容器"：

  const myRef = useRef(initialValue)
  // myRef = { current: initialValue }

两个关键特性：
  1. myRef 在组件的整个生命周期中保持同一个引用
  2. 修改 myRef.current 不会触发重新渲染

对比 useState：
  useState → 值变了 → 重新渲染 → UI 更新
  useRef   → 值变了 → 不渲染   → UI 不变

所以 useRef 用于"幕后数据"——你需要记住，但不需要显示的东西
```

### 5.2 用途 1：访问 DOM

```jsx
import { useRef, useEffect } from 'react'

function AutoFocusInput() {
  const inputRef = useRef(null)  // 创建 ref

  useEffect(() => {
    inputRef.current.focus()     // 通过 .current 访问真实 DOM
  }, [])

  return <input ref={inputRef} />  // 把 ref 绑到 JSX 元素上
}

// 常见 DOM 操作场景：
// - 自动获取焦点
// - 滚动到特定位置：ref.current.scrollIntoView()
// - 测量元素尺寸：ref.current.getBoundingClientRect()
// - 集成第三方 DOM 库（如图表库）
```

### 5.3 用途 2：保存"上一次的值"

```jsx
function Counter() {
  const [count, setCount] = useState(0)
  const prevCountRef = useRef(undefined)

  useEffect(() => {
    prevCountRef.current = count    // 每次渲染后保存当前值
  })
  // 注意没有依赖数组 → 每次渲染后执行
  // 但此时 prevCountRef.current 还是旧值（effect 在渲染后执行）

  return (
    <p>
      当前: {count}，上一次: {prevCountRef.current ?? '无'}
    </p>
  )
}

// 渲染顺序解析：
// 第 1 次渲染：count=0, prevCountRef.current=undefined → 渲染 → effect 把 current 存为 0
// 第 2 次渲染：count=1, prevCountRef.current=0（上次存的）→ 渲染 → effect 把 current 存为 1
// 第 3 次渲染：count=2, prevCountRef.current=1 → ...
```

### 5.4 用途 3：在不重新渲染的情况下保存值

```jsx
function StopWatch() {
  const [time, setTime] = useState(0)
  const [isRunning, setIsRunning] = useState(false)
  const timerRef = useRef(null)  // 存定时器 ID

  const start = () => {
    setIsRunning(true)
    timerRef.current = setInterval(() => {
      setTime(prev => prev + 1)
    }, 1000)
  }

  const stop = () => {
    setIsRunning(false)
    clearInterval(timerRef.current)    // 用 ref 取回定时器 ID
  }

  const reset = () => {
    stop()
    setTime(0)
  }

  // ⭐ 为什么 timerRef 不用 useState？
  // 因为定时器 ID 不需要显示在 UI 上
  // 用 useState 存它 → 每次赋值都触发重新渲染 → 浪费
  // 用 useRef 存它 → 赋值不触发渲染 → 但随时能取到最新值

  return (
    <div>
      <p>{time}s</p>
      <button onClick={isRunning ? stop : start}>{isRunning ? '暂停' : '开始'}</button>
      <button onClick={reset}>重置</button>
    </div>
  )
}
```

### 5.5 useState vs useRef 决策

```
                需要显示在 UI 上吗？
                      │
              ┌───────┴───────┐
              是              否
              ↓               ↓
          useState       需要在渲染之间保持吗？
                              │
                      ┌───────┴───────┐
                      是              否
                      ↓               ↓
                   useRef         普通变量

  useState 示例：count、todos、loading、input value
  useRef 示例：定时器 ID、DOM 引用、上一次的 props/state、WebSocket 实例
  普通变量示例：filteredList、格式化后的字符串
```

---

## 6. useContext：跨层级传数据

### 6.1 解决什么问题

```
问题：Props 层层传递（Prop Drilling）

  App → Dashboard → Sidebar → UserMenu → Avatar
  如果 Avatar 需要 user 数据 → 每一层都要传 user prop → 中间层根本不用 user

        App (user)
         ↓ props: user
      Dashboard (user)         ← 只是透传，自己根本不用
         ↓ props: user
       Sidebar (user)          ← 只是透传，自己根本不用
         ↓ props: user
      UserMenu (user)           ← 只是透传，自己根本不用
         ↓ props: user
       Avatar (user)            ← 终于到了需要的组件

  Context 让你可以跳过中间层，直接传到需要的组件
```

### 6.2 三步走：创建 → 提供 → 消费

```jsx
import { createContext, useContext, useState } from 'react'

// ————— Step 1：创建 Context —————
const ThemeContext = createContext('light')  // 参数是默认值（没有 Provider 时用）

// ————— Step 2：在顶层提供 —————
function App() {
  const [theme, setTheme] = useState('dark')

  return (
    // Provider 包裹的所有后代组件都能访问 value
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <Dashboard />       {/* Dashboard 及其所有后代都能用 theme */}
    </ThemeContext.Provider>
  )
}

// ————— Step 3：在任意后代中消费 —————
function DeepButton() {
  // 不管隔了多少层，直接读取最近的 Provider 的 value
  const { theme, setTheme } = useContext(ThemeContext)

  return (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      style={{ background: theme === 'dark' ? '#333' : '#fff' }}
    >
      当前主题: {theme}
    </button>
  )
}
```

### 6.3 封装 Context（推荐模式）

```jsx
// 实际项目中，把 Context 封装成自定义 Hook + Provider，更整洁

// ————— theme-context.jsx —————
const ThemeContext = createContext(null)

// 自定义 Provider（包含状态逻辑）
export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState('light')
  const toggle = () => setTheme(t => t === 'light' ? 'dark' : 'light')

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  )
}

// 自定义 Hook（使用更方便 + 类型检查）
export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme 必须在 ThemeProvider 内部使用')
  return ctx
}

// ————— 使用 —————
// App.jsx
function App() {
  return (
    <ThemeProvider>
      <Page />
    </ThemeProvider>
  )
}

// 任意后代组件
function Header() {
  const { theme, toggle } = useTheme()  // 一行搞定，无需 import Context
  return <button onClick={toggle}>{theme}</button>
}
```

### 6.4 Context 的局限性 ⭐

```
⚠️ Context 不是万能的状态管理！

  性能问题：
    Provider 的 value 变化 → 所有消费了该 Context 的组件都重新渲染
    即使某个组件只用了 value 的一部分

    举例：
      value={{ theme, user, language }}
      → theme 变了 → 只用了 user 的组件也重新渲染 → 浪费

  适用场景：
    ✅ 少量、低频变化的全局数据
      → 主题（dark/light）
      → 当前用户信息
      → 语言/国际化设置

  不适用场景：
    ❌ 频繁变化的数据（如实时计数器、动画状态）
    ❌ 大量全局状态
    → 用 Zustand 等状态管理库（阶段 7）

  缓解方式：
    1. 拆分 Context：主题一个 Context，用户一个 Context
    2. 用 useMemo 缓存 value 对象：避免每次渲染创建新对象
```

---

## 7. useReducer：复杂状态逻辑

### 7.1 什么时候用 useReducer

```
useState 足够应对大多数简单场景，但当遇到：
  → 多个相关联的 state（loading + data + error）
  → 多种操作类型（增/删/改/排序/筛选）
  → 下一个 state 依赖上一个 state 的多个字段

就该考虑 useReducer 了。

useState   = "给你一个值和一个设值函数"
useReducer = "给你一个状态和一个分发函数，所有状态变更逻辑集中在 reducer 里"
```

### 7.2 基本用法

```jsx
import { useReducer } from 'react'

// ① 定义 reducer：(旧状态, 动作) => 新状态
function todoReducer(state, action) {
  switch (action.type) {
    case 'add':
      return {
        ...state,
        todos: [...state.todos, {
          id: Date.now(), text: action.payload, done: false
        }]
      }
    case 'toggle':
      return {
        ...state,
        todos: state.todos.map(t =>
          t.id === action.payload ? { ...t, done: !t.done } : t
        )
      }
    case 'delete':
      return {
        ...state,
        todos: state.todos.filter(t => t.id !== action.payload)
      }
    case 'set_filter':
      return { ...state, filter: action.payload }
    default:
      throw new Error(`未知 action: ${action.type}`)
  }
}

// ② 在组件中使用
function TodoApp() {
  const [state, dispatch] = useReducer(todoReducer, {
    todos: [],          // 初始状态
    filter: 'all'
  })

  return (
    <div>
      <button onClick={() => dispatch({ type: 'add', payload: '新任务' })}>
        添加
      </button>
      <ul>
        {state.todos.map(t => (
          <li key={t.id}>
            <span onClick={() => dispatch({ type: 'toggle', payload: t.id })}>
              {t.done ? '✅' : '⬜'} {t.text}
            </span>
            <button onClick={() => dispatch({ type: 'delete', payload: t.id })}>
              删除
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

### 7.3 useReducer 的优势

```
1. 状态逻辑集中
   → 所有"怎么改 state"的逻辑都在 reducer 里
   → 组件只负责"什么时候触发"（dispatch）
   → 类似 Vue 的 Pinia actions

2. 可测试
   → reducer 是纯函数：(state, action) => newState
   → 可以脱离 React 单独测试

3. 可预测
   → 所有操作都有明确的 type
   → 容易追踪"是什么操作导致了状态变化"

4. 避免"多个 setState 不同步"的问题
   → 一个 dispatch 就把所有相关状态一起更新
```

### 7.4 useState vs useReducer 决策

```
                 有几个相关的 state？
                        │
                ┌───────┴───────┐
              1-2 个          3 个以上
                ↓               ↓
          更新逻辑复杂吗？   useReducer
                │
        ┌───────┴───────┐
        否              是
        ↓               ↓
    useState        useReducer

  简单示例 → useState：
    const [count, setCount] = useState(0)
    const [name, setName] = useState('')

  复杂示例 → useReducer：
    const [state, dispatch] = useReducer(reducer, {
      todos: [], filter: 'all', loading: false, error: null
    })
```

### 7.5 和 Vue 的对比

```
useReducer           ≈    Pinia 的 actions + state
  reducer 函数       ≈    action 函数
  dispatch           ≈    调用 action
  action.type        ≈    action 方法名
  state              ≈    store state

但 useReducer 更轻量——不需要安装额外库，一个函数就搞定
适合组件级别的复杂状态，不适合全局状态管理（那个用 Zustand，阶段 7 详讲）
```

---

## 8. Hooks 规则

### 8.1 两条铁律

```
规则 1：只在组件函数的顶层调用 Hook
  ❌ if (condition) { useState(...) }    // 条件里
  ❌ for (...) { useEffect(...) }        // 循环里
  ❌ handleClick 里 { useState(...) }    // 事件处理函数里
  ❌ 嵌套函数里 { useContext(...) }      // 嵌套函数里

  ✅ 在函数组件的最外层，按固定顺序调用

  为什么？
  React 在内部用一个"数组"来存储每个 Hook 的状态
  第 1 次渲染：Hook 调用顺序是 [0, 1, 2, 3]
  第 2 次渲染：React 按同样的顺序 [0, 1, 2, 3] 取回状态
  如果有条件跳过了某个 Hook → 顺序变成 [0, 2, 3] → 状态全部错位！


规则 2：只在 React 函数组件或自定义 Hook 中调用
  ❌ 普通函数里调用 useState
  ❌ class 组件里调用 useEffect

  ✅ 函数组件里：function App() { useState(...) }
  ✅ 自定义 Hook 里：function useMyHook() { useState(...) }
```

### 8.2 ESLint 插件

```
安装 eslint-plugin-react-hooks 可以自动检查这两条规则

还有一条额外的规则（exhaustive-deps）：
  → 自动检查 useEffect 的依赖数组是否完整
  → 如果 effect 里用了 state/props 但没放进依赖 → 警告
  → 强烈建议开启，能避免 90% 的 useEffect bug
```

---

## 9. Hooks 选择决策树

```
你要解决什么问题？

  "需要在渲染之间保持一个值，并且值变化时 UI 要更新"
    → useState

  "state 逻辑很复杂（多字段、多操作类型）"
    → useReducer

  "需要在渲染后做副作用（请求、订阅、DOM 操作）"
    → useEffect

  "需要保持一个值，但不需要触发渲染"
    → useRef

  "需要访问真实 DOM 节点"
    → useRef + ref prop

  "需要跨多层传数据，避免 prop drilling"
    → useContext

  "需要缓存昂贵的计算结果"
    → useMemo（阶段 7）

  "需要缓存函数引用（配合 React.memo）"
    → useCallback（阶段 7）
```

---

## 10. 面试常问

### Q1: useEffect 的依赖数组是什么？不同依赖有什么区别？

**答**：
- `useEffect(fn)` — 无依赖，每次渲染后执行
- `useEffect(fn, [])` — 空依赖，仅挂载时执行一次
- `useEffect(fn, [a, b])` — a 或 b 变化时执行
- React 用 `Object.is()` 比较每个依赖和上次的值，任何一个不同就重新执行 effect
- 依赖必须写完整（ESLint exhaustive-deps 规则），否则会遇到闭包陷阱

### Q2: 什么是闭包陷阱？怎么解决？

**答**：
- 闭包陷阱指 useEffect 或定时器的回调函数"记住"了创建时的 state 值（闭包），导致使用过期数据
- 根本原因：函数组件每次渲染创建新的变量快照，旧的回调函数闭包着旧快照
- 解决方案：
  1. 把依赖加进 useEffect 的依赖数组（effect 重新执行就拿到新闭包）
  2. 用 useRef 保存最新值（ref 是可变容器，闭包捕获 ref 引用，但 .current 总是最新）
  3. 用函数式 setState（`prev => prev + 1`，不依赖闭包中的值）

### Q3: useEffect 和 useLayoutEffect 的区别？

**答**：
- `useEffect`：异步执行，在浏览器绘制之后。不阻塞页面渲染，**绝大多数情况用这个**
- `useLayoutEffect`：同步执行，在 DOM 更新之后但浏览器绘制之前。用于需要在用户看到画面前操作 DOM 的场景（如测量元素尺寸、防止闪烁）
- 如果你不确定用哪个，用 useEffect

### Q4: useRef 和 useState 的区别？

**答**：

| | useState | useRef |
|--|---------|--------|
| 修改后是否重新渲染 | ✅ 是 | ❌ 否 |
| 值何时更新 | 下次渲染 | 立即（.current 直接修改） |
| 用途 | UI 上显示的数据 | 幕后数据（定时器ID、DOM、上次值） |
| 返回值 | `[value, setter]` | `{ current: value }` |

一句话：state 是"给用户看的数据"，ref 是"给程序用的数据"。

### Q5: Context 的性能问题是什么？怎么解决？

**答**：
- Provider 的 value 一变，所有消费该 Context 的组件都重新渲染，即使只用了 value 的一部分
- 解决方案：
  1. 拆分 Context（theme 一个、user 一个，变化互不影响）
  2. 用 useMemo 缓存 value 对象（避免每次渲染创建新引用）
  3. 频繁更新的数据用 Zustand 替代（选择性订阅，只有读了该字段的组件才重新渲染）

### Q6: useState 和 useReducer 怎么选？

**答**：
- 1-2 个简单独立的状态 → useState
- 3 个以上关联状态，或更新逻辑复杂（多种操作类型）→ useReducer
- useReducer 的 reducer 是纯函数，可以脱离 React 单独测试
- useReducer 保证一个 dispatch 更新所有相关字段，不会出现中间状态

---

## 11. 练习

```
useEffect：
  1. 用 useEffect + fetch 请求 jsonplaceholder 的 /users，展示用户列表
     → 要求处理 loading + error + 竞态
  2. 写一个倒计时组件（从 10 到 0），到 0 自动停止
     → 要求：切走页面时清理定时器
     → 思考：为什么 setInterval 里必须用函数式更新？
  3. 用 useEffect 监听 window 的 resize 事件，实时显示窗口宽高
     → 卸载时移除监听器

useRef：
  4. 自动聚焦：页面加载后 input 自动获取焦点
  5. 保存"上一次的值"：显示 "count 从 X 变到了 Y"
  6. 写一个秒表组件（开始/暂停/重置），定时器 ID 存在 useRef 里

useContext：
  7. 实现主题切换（dark/light）
     → 封装成 ThemeProvider + useTheme 自定义 Hook
     → 在 3 个以上的组件中消费 theme

useReducer：
  8. 把阶段 2 的 TodoApp 用 useReducer 重写
     → state = { todos, filter }
     → actions: add, delete, toggle, set_filter
     → 对比和 useState 版本的代码量和清晰度

综合：
  9. 写一个"用户搜索"功能：
     → 输入框（useState）+ 防抖（useRef 存定时器）+ 请求（useEffect）
     → 展示搜索结果列表
```

---

## 📖 推荐学习路径

1. 阅读 [react.dev - Synchronizing with Effects](https://react.dev/learn/synchronizing-with-effects)
2. 阅读 [react.dev - You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect)
3. 阅读 Dan Abramov 的 [A Complete Guide to useEffect](https://overreacted.io/a-complete-guide-to-useeffect/)
4. 确保会写：数据请求 + 清理、定时器 + 清理、闭包陷阱的 3 种修复方式

---

## 🔗 为什么接下来学 TypeScript？

```
到这里你已经掌握了 React 的核心能力：useState、useEffect、useRef、useContext、useReducer。

但你可能已经注意到一些"隐患"：
  → Props 传错了类型（string 传成了 number），运行时才发现
  → useContext 的 value 结构不清楚，IDE 没有任何提示
  → API 返回的数据字段拼错了，代码不报错但页面空白

下一阶段用 TypeScript 解决这些问题——让 IDE 在你写代码时就告诉你哪里错了。
```

> ⬅️ [上一阶段：第一个完整组件](./02-first-component.md) | ➡️ [下一阶段：TypeScript + React](./04-typescript-react.md)
