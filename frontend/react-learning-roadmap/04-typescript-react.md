# 阶段 4：TypeScript + React（1 天）

> **一句话定位**：TypeScript 不是 React 的附加品，而是现代 React 开发的标配。本阶段让你掌握 React + TS 的常用类型写法，从此所有新代码都用 TS。

> 📌 阶段 2-3 的代码用 JS 写完全没问题，不需要回去改。从现在起新代码全用 TS 写——练习 1 就是把之前的 TodoApp 迁移到 TS，作为桥接。

---

## 目录

- [1. 为什么 React + TypeScript](#1-为什么-react--typescript)
- [2. 项目搭建](#2-项目搭建)
- [3. Props 类型](#3-props-类型)
- [4. State 类型](#4-state-类型)
- [5. 事件类型](#5-事件类型)
- [6. Ref 类型](#6-ref-类型)
- [7. Context 类型](#7-context-类型)
- [8. 常用工具类型](#8-常用工具类型)
- [9. 泛型组件](#9-泛型组件)
- [10. 类型速查表](#10-类型速查表)
- [11. 面试常问](#11-面试常问)
- [12. 练习](#12-练习)

---

## 1. 为什么 React + TypeScript

### 1.1 TS 带来什么

```
没有 TS 时的真实痛苦：

  1. Props 传错了类型，运行时才发现
     <UserCard name={42} />  // name 应该是 string，传了 number
     → 不报错，直到页面显示 42 才察觉

  2. 回调函数签名不确定
     <SearchBox onChange={???} />
     → onChange 接收什么参数？返回什么？看源码才知道

  3. API 返回数据结构不清楚
     const data = await fetch('/api/users').then(r => r.json())
     → data.name 还是 data.username？拼错了也不报错

有了 TS 之后：
  ✅ 写代码时 IDE 实时告诉你 Props 该传什么
  ✅ 回调函数的参数类型一目了然
  ✅ API 数据有类型定义，拼错立刻报红
  ✅ 重构时自动发现所有受影响的地方
```

### 1.2 TS 只在编译时工作

```
一个关键认知：TypeScript 的类型只在编译时检查，运行时全部消失

  .tsx 文件 → TypeScript 编译器 → .jsx 文件（类型全部被删除） → 浏览器执行

  所以 TS 不会让你的代码变慢（运行时没有任何类型检查开销）
  它只是一个"更聪明的 Linter"——帮你在写代码时就发现错误
```

---

## 2. 项目搭建

### 2.1 用 Vite 创建 React + TS 项目

```bash
# 创建项目
npm create vite@latest my-app -- --template react-ts

# 进入目录并安装
cd my-app
npm install
npm run dev
```

### 2.2 文件扩展名

```
.ts   → 纯 TypeScript 文件（工具函数、类型定义、API 层）
.tsx  → 包含 JSX 的 TypeScript 文件（React 组件）

规则很简单：
  有 JSX → .tsx
  没 JSX → .ts
```

### 2.3 tsconfig 关键配置

```json
{
  "compilerOptions": {
    "strict": true,          // ⭐ 开启严格模式（推荐，虽然一开始会多一些报错）
    "jsx": "react-jsx",      // 支持新的 JSX 转换（不需要 import React）
    "esModuleInterop": true, // 兼容 CommonJS 模块的默认导入
    "skipLibCheck": true     // 跳过 node_modules 的类型检查（加快编译）
  }
}
```

---

## 3. Props 类型

### 3.1 基本 Props 类型

```tsx
// ⭐ 用 interface 定义 Props 类型（React 社区惯例）
interface UserCardProps {
  name: string                    // 必填
  age: number                     // 必填
  isOnline?: boolean              // 可选（?:）
  role: 'admin' | 'user' | 'guest'  // 联合类型（限定取值范围）
  onLogout: () => void            // 无参回调
  onRename: (newName: string) => void  // 有参回调
}

function UserCard({ name, age, isOnline = false, role, onLogout, onRename }: UserCardProps) {
  //                                        ↑ 可选 props 的默认值
  return (
    <div>
      <h2>{name}（{age}岁）- {role}</h2>
      {isOnline && <span>🟢</span>}
      <button onClick={onLogout}>退出</button>
      <button onClick={() => onRename('新名字')}>改名</button>
    </div>
  )
}

// 使用时 IDE 自动检查：
<UserCard
  name="张三"
  age={25}         // ✅
  age="25"         // ❌ 类型错误：string 不能赋给 number
  role="admin"     // ✅
  role="superadmin" // ❌ 不在联合类型范围内
  onLogout={() => {}}   // ✅
  onRename={(n) => {}}  // ✅ n 自动推断为 string
/>
```

### 3.2 children 类型

```tsx
// React.ReactNode：可以是任何合法的 JSX 子元素
interface CardProps {
  title: string
  children: React.ReactNode   // string | number | JSX | null | undefined | boolean | 数组
}

function Card({ title, children }: CardProps) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  )
}

// 使用：
<Card title="信息">
  <p>文本</p>          {/* ✅ JSX */}
  {'字符串'}            {/* ✅ string */}
  {42}                  {/* ✅ number */}
  {null}                {/* ✅ null */}
</Card>
```

### 3.3 interface vs type

```tsx
// 两种定义 Props 类型的方式：

// ① interface（推荐用于 Props）
interface ButtonProps {
  text: string
  variant: 'primary' | 'secondary'
}

// ② type（用于复杂类型运算）
type ButtonProps = {
  text: string
  variant: 'primary' | 'secondary'
}

// 区别：
// interface 可以 extends 继承，可被重复声明自动合并
// type 可以做联合/交叉/条件类型等复杂运算
// React 社区惯例：Props 用 interface，工具类型用 type
// 实际上两者在 Props 场景下几乎没区别，选一个统一用就好
```

### 3.4 Props 继承与组合

```tsx
// 场景：一个组件的 Props 基于另一个扩展
interface BaseButtonProps {
  text: string
  disabled?: boolean
}

// extends 继承
interface IconButtonProps extends BaseButtonProps {
  icon: string
}

// 交叉类型（& 运算）
type IconButtonProps = BaseButtonProps & {
  icon: string
}

// 继承 HTML 元素的原生属性
interface CustomInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
}

function CustomInput({ label, error, ...inputProps }: CustomInputProps) {
  return (
    <div>
      <label>{label}</label>
      <input {...inputProps} />    {/* 所有原生 input 属性都透传 */}
      {error && <span className="error">{error}</span>}
    </div>
  )
}

// 使用时自动支持所有 <input> 原生属性：
<CustomInput label="邮箱" type="email" placeholder="输入邮箱" required />
```

---

## 4. State 类型

### 4.1 自动推断 vs 显式指定

```tsx
// 大多数情况 TS 可以从初始值自动推断类型：
const [count, setCount] = useState(0)           // 推断为 number ✅
const [name, setName] = useState('张三')        // 推断为 string ✅
const [isOpen, setIsOpen] = useState(false)     // 推断为 boolean ✅

// 以下情况需要显式指定泛型：

// ① 初始值是 null（后续会变成其他类型）
const [user, setUser] = useState<User | null>(null)
//                               ↑ 没有泛型的话，TS 推断为 null，setUser(userData) 会报错

// ② 初始值是空数组（TS 推断为 never[]）
const [todos, setTodos] = useState<Todo[]>([])
//                                 ↑ 没有泛型的话，TS 推断为 never[]，push 任何东西都报错

// ③ 联合类型
const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
```

### 4.2 定义数据类型

```tsx
// 先定义数据结构类型（通常放在单独的 types.ts 文件里）
interface Todo {
  id: number
  text: string
  done: boolean
  createdAt: Date
}

interface User {
  id: number
  name: string
  email: string
  role: 'admin' | 'user'
}

// 然后在组件中使用
function TodoApp() {
  const [todos, setTodos] = useState<Todo[]>([])

  const handleAdd = (text: string) => {
    const newTodo: Todo = {
      id: Date.now(),
      text,
      done: false,
      createdAt: new Date()
    }
    setTodos(prev => [...prev, newTodo])   // TS 自动检查 newTodo 是否符合 Todo 类型
  }

  return (/* ... */)
}
```

---

## 5. 事件类型

### 5.1 常用事件类型

```tsx
function EventDemo() {

  // 表单元素变化
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    console.log(e.target.value)     // TS 知道 e.target 是 HTMLInputElement
  }

  // 表单提交
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
  }

  // 鼠标点击
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    console.log(e.clientX, e.clientY)
  }

  // 键盘事件
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') { /* ... */ }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input onChange={handleChange} onKeyDown={handleKeyDown} />
      <button onClick={handleClick}>提交</button>
    </form>
  )
}
```

### 5.2 偷懒技巧：let TS 推断

```tsx
// 不想记事件类型？完全可以让 TS 自己推断：

// 方式 1：内联写，TS 自动推断 e 的类型
<input onChange={(e) => setName(e.target.value)} />
//                ↑ TS 自动推断为 React.ChangeEvent<HTMLInputElement>

// 方式 2：先内联写，hover 看类型，再提取成独立函数
// IDE 里 hover e → 看到类型 → 复制到独立函数的参数上

// 实际上大多数事件处理直接内联写就够了
// 只有逻辑复杂到需要提取独立函数时，才需要写类型
```

---

## 6. Ref 类型

### 6.1 DOM Ref

```tsx
// 引用 DOM 元素时需要指定元素类型
const inputRef = useRef<HTMLInputElement>(null)
//                      ↑ HTML 元素类型

useEffect(() => {
  inputRef.current?.focus()    // TS 知道 current 可能是 null，用 ?. 安全访问
  //              ↑ 可选链：current 为 null 时不报错
}, [])

return <input ref={inputRef} />

// 常用 DOM 元素类型：
// HTMLInputElement   → <input>
// HTMLButtonElement  → <button>
// HTMLDivElement     → <div>
// HTMLFormElement    → <form>
// HTMLAnchorElement  → <a>
// HTMLTextAreaElement → <textarea>
// HTMLSelectElement  → <select>
```

### 6.2 值 Ref

```tsx
// 存储非 DOM 值时，传初始值（不传 null）
const timerRef = useRef<number | null>(null)
//                      ↑ 定时器 ID 是 number

const start = () => {
  timerRef.current = window.setInterval(() => { /* ... */ }, 1000)
}

const stop = () => {
  if (timerRef.current !== null) {
    clearInterval(timerRef.current)
  }
}

// 存上一次的值
const prevCountRef = useRef<number | undefined>(undefined)
```

---

## 7. Context 类型

### 7.1 完整的 Context + TS 模式

```tsx
// ————— types.ts —————
interface ThemeContextType {
  theme: 'light' | 'dark'
  toggleTheme: () => void
}

// ————— theme-context.tsx —————
import { createContext, useContext, useState, ReactNode } from 'react'

// 创建 Context（初始值给 null，用自定义 Hook 做安全检查）
const ThemeContext = createContext<ThemeContextType | null>(null)

// Provider 组件
interface ThemeProviderProps {
  children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const toggleTheme = () => setTheme(t => t === 'light' ? 'dark' : 'light')

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

// 自定义 Hook（类型安全 + 错误提示）
export function useTheme(): ThemeContextType {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return ctx   // TS 知道这里 ctx 不是 null，返回类型是 ThemeContextType
}

// ————— 使用 —————
function Header() {
  const { theme, toggleTheme } = useTheme()
  //      ↑ TS 自动补全，知道有 theme 和 toggleTheme
  return <button onClick={toggleTheme}>当前: {theme}</button>
}
```

---

## 8. 常用工具类型

### 8.1 React 内置类型

```tsx
// React.ReactNode：任何可以渲染的内容
// 用于 children、可渲染的 props
type ReactNode = string | number | boolean | null | undefined | React.ReactElement | React.ReactNode[]

// React.ReactElement：一个 JSX 元素
// 比 ReactNode 更严格，不包括 string/number/null 等
const element: React.ReactElement = <div>Hello</div>

// React.FC（不推荐，但你会在老代码里见到）
const OldStyle: React.FC<Props> = ({ name }) => <div>{name}</div>
// ❌ 不推荐原因：隐式添加 children、泛型组件写不了
// ✅ 直接用函数声明 + Props 类型参数
```

### 8.2 TypeScript 内置工具类型

```tsx
interface User {
  id: number
  name: string
  email: string
  role: 'admin' | 'user'
}

// Partial<T>：所有属性变可选
type UpdateUser = Partial<User>
// = { id?: number; name?: string; email?: string; role?: ... }

// Pick<T, K>：只取部分属性
type UserPreview = Pick<User, 'id' | 'name'>
// = { id: number; name: string }

// Omit<T, K>：排除部分属性
type CreateUser = Omit<User, 'id'>
// = { name: string; email: string; role: ... }

// Record<K, V>：键值对映射
type Themes = Record<'light' | 'dark', { bg: string; text: string }>
// = { light: { bg: string; text: string }; dark: { bg: string; text: string } }

// 实际用途示例：
function updateUser(id: number, updates: Partial<User>) { /* ... */ }
updateUser(1, { name: '新名字' })       // ✅ 只传需要更新的字段
updateUser(1, { name: '新名字', age: 30 }) // ❌ User 没有 age 属性
```

---

## 9. 泛型组件

### 9.1 为什么需要泛型组件

```tsx
// 场景：一个通用的列表组件，可以渲染任意类型的数据

// ❌ 用 any：丢失了类型信息
interface ListProps {
  items: any[]
  renderItem: (item: any) => React.ReactNode
}

// ✅ 用泛型：保留了类型信息
interface ListProps<T> {
  items: T[]
  renderItem: (item: T) => React.ReactNode
  keyExtractor: (item: T) => string | number
}
```

### 9.2 泛型组件写法

```tsx
function List<T>({ items, renderItem, keyExtractor }: ListProps<T>) {
  return (
    <ul>
      {items.map(item => (
        <li key={keyExtractor(item)}>{renderItem(item)}</li>
      ))}
    </ul>
  )
}

// 使用时 TS 自动推断 T 的类型：
interface User { id: number; name: string }

<List
  items={users}                     // T 被推断为 User
  renderItem={(user) => (           // user 自动推断为 User
    <span>{user.name}</span>        // TS 知道 user 有 name 属性
  )}
  keyExtractor={(user) => user.id}  // user 自动推断为 User
/>

// 另一个例子：通用的 Select 组件
interface SelectProps<T> {
  options: T[]
  value: T
  onChange: (value: T) => void
  getLabel: (option: T) => string
  getValue: (option: T) => string | number
}

function Select<T>({ options, value, onChange, getLabel, getValue }: SelectProps<T>) {
  return (
    <select
      value={String(getValue(value))}
      onChange={e => {
        const selected = options.find(o => String(getValue(o)) === e.target.value)
        if (selected) onChange(selected)
      }}
    >
      {options.map(option => (
        <option key={String(getValue(option))} value={String(getValue(option))}>
          {getLabel(option)}
        </option>
      ))}
    </select>
  )
}
```

---

## 10. 类型速查表

```tsx
// ————— Props —————
interface Props {
  // 基本类型
  name: string
  age: number
  isActive: boolean

  // 可选
  subtitle?: string

  // 联合类型
  status: 'idle' | 'loading' | 'error'

  // 数组
  items: string[]
  users: User[]

  // 对象
  style: React.CSSProperties
  config: { key: string; value: number }

  // 函数
  onClick: () => void
  onChange: (value: string) => void
  onSubmit: (data: FormData) => Promise<void>

  // children
  children: React.ReactNode
}

// ————— Hooks —————
useState<string>('')
useState<number>(0)
useState<User | null>(null)
useState<Todo[]>([])
useState<'light' | 'dark'>('light')

useRef<HTMLInputElement>(null)
useRef<HTMLDivElement>(null)
useRef<number | null>(null)

// ————— 事件 —————
React.ChangeEvent<HTMLInputElement>
React.FormEvent<HTMLFormElement>
React.MouseEvent<HTMLButtonElement>
React.KeyboardEvent<HTMLInputElement>

// ————— 提示 —————
// 不确定类型时：
// 1. 内联写 → hover 看 TS 推断的类型
// 2. 搜索：react typescript cheatsheet
```

---

## 11. 面试常问

### Q1: React 中 interface 和 type 怎么选？

**答**：
- React 社区惯例是 Props 用 `interface`（可继承、可声明合并），工具类型用 `type`（支持联合/交叉/条件类型）
- 在 Props 场景下两者几乎没有区别，团队内统一即可
- 如果需要继承 HTML 原生属性（`extends React.InputHTMLAttributes`），必须用 `interface`

### Q2: useState 什么时候需要写泛型？

**答**：
- 初始值能推断类型时不用写（`useState(0)`、`useState('')`）
- 初始值是 `null` 但后续会变成其他类型时要写（`useState<User | null>(null)`）
- 初始值是空数组时要写（`useState<Todo[]>([])`）
- 需要限定值的范围时要写（`useState<'a' | 'b'>('a')`）

### Q3: 怎么给事件处理函数定类型？

**答**：
- 最简单的方式：内联写，让 TS 自动推断（`onChange={(e) => ...}`，`e` 的类型自动推断）
- 需要提取成独立函数时：`(e: React.ChangeEvent<HTMLInputElement>) => void`
- 记不住类型名时：先内联写 → hover 看推断结果 → 复制类型到独立函数

---

## 12. 练习

```
基础：
  1. 把阶段 2 的 TodoApp 完整迁移到 TypeScript
     → 定义 Todo interface
     → 所有 Props、State、事件处理函数都加上类型
     （这是检验本阶段的核心标准）

  2. 给 useContext 的主题切换加上完整 TS 类型
     → ThemeContext 类型定义
     → ThemeProvider 组件
     → useTheme 自定义 Hook

进阶：
  3. 写一个泛型的 List<T> 组件
     → 接受 items: T[], renderItem, keyExtractor
     → 用不同数据类型（User[], Product[]）测试

  4. 写一个 CustomInput 组件
     → 继承 HTMLInputElement 的所有原生属性
     → 额外加 label 和 error 两个自定义 Props
     → 使用 {...inputProps} 透传原生属性

  5. 为阶段 3 的 useFetch Hook 加上泛型
     → function useFetch<T>(url: string): { data: T | null; loading: boolean; error: string | null }
```

---

## 📖 推荐学习路径

1. [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app/) — 最实用的速查手册
2. [react.dev - Using TypeScript](https://react.dev/learn/typescript) — 官方 TS 指南
3. 核心：记住 Props interface + useState 泛型 + 事件类型这三个最高频场景即可

> ⬅️ [上一阶段：Hooks 深度理解](./03-hooks-deep-dive.md) | ➡️ [下一阶段：组件设计 & 复用模式](./05-component-patterns.md)
