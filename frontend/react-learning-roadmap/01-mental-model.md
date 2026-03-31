# 阶段 1：核心心智模型 + 渲染机制（半天）

> **一句话定位**：建立 React 最核心的思维方式。理解了这一章，后面所有知识都是在这个框架上添砖加瓦。

---

## 目录

- [1. React 解决什么问题](#1-react-解决什么问题)
- [2. UI = f(state)](#2-ui--fstate)
- [3. 声明式 vs 命令式](#3-声明式-vs-命令式)
- [4. 虚拟 DOM](#4-虚拟-dom)
- [5. 渲染流程全景](#5-渲染流程全景)
- [6. 单向数据流](#6-单向数据流)
- [7. 和 Vue 的对比](#7-和-vue-的对比)
- [8. 常见误解澄清](#8-常见误解澄清)
- [9. 面试常问](#9-面试常问)
- [10. 练习](#10-练习)

---

## 1. React 解决什么问题

### 1.1 没有框架时的痛苦

假设你要做一个简单的计数器页面：

```html
<!-- 原生 JS / jQuery 时代 -->
<div id="app">
  <p id="count-display">计数: 0</p>
  <button id="add-btn">+1</button>
  <button id="reset-btn">重置</button>
</div>

<script>
  let count = 0

  document.getElementById('add-btn').addEventListener('click', () => {
    count++
    document.getElementById('count-display').textContent = `计数: ${count}`
  })

  document.getElementById('reset-btn').addEventListener('click', () => {
    count = 0
    document.getElementById('count-display').textContent = `计数: ${count}`
  })
</script>
```

**问题在哪？**

```
这个例子才 2 个按钮就已经暴露了问题：

1. 状态（count）和 UI 更新（textContent）是手动同步的
   → 每次改 count，你都要手动更新对应的 DOM
   → 如果有 10 个地方显示 count，你要更新 10 次

2. 代码里混杂了"数据逻辑"和"DOM 操作"
   → 随着功能增加，代码会变成意大利面条

3. 没有统一的模式
   → 团队里每个人的写法不一样
   → 维护成本随功能线性增长
```

### 1.2 React 的解法

```jsx
// React 版本
function Counter() {
  const [count, setCount] = useState(0)

  return (
    <div>
      <p>计数: {count}</p>
      <button onClick={() => setCount(count + 1)}>+1</button>
      <button onClick={() => setCount(0)}>重置</button>
    </div>
  )
}
```

**对比一下：**

```
你只做了一件事：声明 "count 是几，UI 长什么样"
你没有做的事：找 DOM、改 DOM、手动同步

React 帮你处理了所有 DOM 操作。
你只管 state，React 帮你更新 UI。
```

> 🔑 **这就是 React 存在的理由**：把"状态管理"和"DOM 操作"彻底分开，你只管前者，React 管后者。

---

## 2. UI = f(state)

### 2.1 核心公式

这是 React 最核心的一句话，理解了它就理解了 React 的 80%：

```
UI = f(state)

翻译成人话：
  UI 是 state 的函数
  → 同样的 state，永远渲染出同样的 UI
  → state 变了，UI 自动跟着变
```

### 2.2 组件就是函数

在 React 中，"函数"指的就是你的组件：

```jsx
//       f        (state)
function Greeting({ name }) {
  // 输入(state/props) → 输出(UI)
  return <h1>Hello, {name}!</h1>
}

// state = { name: "张三" }  →  UI = <h1>Hello, 张三!</h1>
// state = { name: "李四" }  →  UI = <h1>Hello, 李四!</h1>
```

### 2.3 "快照"心智模型 ⭐

这是理解 React 最重要的思维方式：

```
每次渲染都是一张"快照"

  第 1 次渲染：count = 0   →   快照：<p>计数: 0</p>
  第 2 次渲染：count = 1   →   快照：<p>计数: 1</p>
  第 3 次渲染：count = 2   →   快照：<p>计数: 2</p>

  每次 setState → React 重新调用组件函数 → 生成新快照 → 对比差异 → 更新 DOM
```

**为什么"快照"很重要？**

```
因为它解释了 React 里很多"反直觉"的行为：

1. 为什么 state 不能直接修改？
   → 因为 React 要对比两张快照的差异，直接修改就没有"旧快照"可对比了

2. 为什么 setState 后取值还是旧的？
   → 因为你在当前这张快照里，新快照要到下次渲染才生成

3. 为什么函数组件每次渲染值都是"新的"？
   → 因为每次渲染都是一次全新的函数调用，产生一套全新的变量
```

### 2.4 和传统编程的区别

```
传统编程（命令式）：
  数据变了 → 你手动改 UI → 数据和 UI 可能不同步

React（声明式）：
  数据变了 → React 自动算出新 UI → 数据和 UI 永远同步

类比：
  命令式 = 你告诉出租车司机 "左转、右转、前行 500 米"
  声明式 = 你告诉出租车司机 "去火车站"
  → 结果一样，但声明式不用关心细节
```

---

## 3. 声明式 vs 命令式

### 3.1 定义

```
命令式 (Imperative)：告诉计算机 "怎么做"
  → 一步一步的指令
  → 你关心的是过程

声明式 (Declarative)：告诉计算机 "要什么"
  → 描述最终结果
  → 你关心的是结果
```

### 3.2 代码对比

```javascript
// 命令式：过滤一个数组
const result = []
for (let i = 0; i < arr.length; i++) {
  if (arr[i] > 5) {
    result.push(arr[i])
  }
}

// 声明式：过滤一个数组
const result = arr.filter(x => x > 5)
// 你只说了"我要大于5的元素"，不关心怎么遍历
```

```jsx
// 命令式更新 UI（jQuery）：
$('#count').text(newCount)
$('#list').append('<li>' + newItem + '</li>')
$('#submit-btn').attr('disabled', true)
// 你要精确地告诉每个 DOM 元素怎么变

// 声明式更新 UI（React）：
return (
  <div>
    <p>{count}</p>
    <ul>{items.map(i => <li key={i.id}>{i.text}</li>)}</ul>
    <button disabled={isSubmitting}>提交</button>
  </div>
)
// 你只描述 UI 应该长什么样，React 算出怎么更新 DOM
```

### 3.3 声明式的代价

```
声明式不是免费的午餐：

优点：
  ✅ 代码更简洁、更易读
  ✅ 不容易出 bug（状态和 UI 自动同步）
  ✅ 更容易推理和测试

代价：
  ⚠️ 需要一个"翻译层"把声明变成命令 → 这就是虚拟 DOM 的角色
  ⚠️ 有性能开销（React 需要 diff 对比）
  ⚠️ 有时候"声明式"反而不直观（比如动画、直接操作 DOM 时）
```

---

## 4. 虚拟 DOM

### 4.1 为什么需要虚拟 DOM？

```
问题：
  你写了声明式代码（"UI 应该长这样"）
  但浏览器只懂命令式操作（"把这个节点的文本改成 X"）
  → 需要有人把"声明"翻译成"命令"

React 的方案：
  1. 在 JS 内存里维护一份 UI 的"镜像"（虚拟 DOM）
  2. state 变化 → 生成新的虚拟 DOM
  3. 新旧虚拟 DOM 做 diff → 算出最小变更
  4. 只把变更部分应用到真实 DOM
```

### 4.2 虚拟 DOM 是什么？

```
虚拟 DOM 不是什么神秘的东西，就是普通的 JS 对象：

JSX：
  <div className="card">
    <h2>标题</h2>
    <p>内容</p>
  </div>

编译后变成：
  React.createElement('div', { className: 'card' }, 
    React.createElement('h2', null, '标题'),
    React.createElement('p', null, '内容')
  )

最终生成的虚拟 DOM（JS 对象）：
  {
    type: 'div',
    props: { className: 'card' },
    children: [
      { type: 'h2', props: {}, children: ['标题'] },
      { type: 'p',  props: {}, children: ['内容'] }
    ]
  }

→ 就是一棵 JS 对象树，描述了 UI 的结构
→ 操作 JS 对象比操作真实 DOM 快得多
```

### 4.3 Diff 算法的关键假设

```
React 的 Diff 不是通用的树对比算法（通用算法是 O(n³) 复杂度），
而是基于两个假设做了简化（O(n) 复杂度）：

假设 1：不同类型的元素产生完全不同的树
  <div> 变成 <span> → 直接销毁旧树，创建新树
  不会尝试"复用"节点

假设 2：key 标识同级元素
  [A, B, C] → [A, C, B]
  没有 key → React 以为 B 变成了 C，C 变成了 B → 更新两个节点
  有了 key → React 知道只是 B 和 C 换了位置 → 移动即可

⭐ 这就是为什么列表渲染必须加 key！
```

### 4.4 虚拟 DOM 的常见误解

```
❌ 误解 1："虚拟 DOM 比真实 DOM 快"
✅ 真相：虚拟 DOM 不比直接操作 DOM 快
   → 直接操作一个节点，肯定比"先算 diff 再操作"快
   → 虚拟 DOM 的价值不是"快"，而是让声明式编程变得可行
   → 它用可接受的性能代价换来了更好的开发体验

❌ 误解 2："React 会重新创建整个 DOM"
✅ 真相：React 只更新变化的部分
   → "重新渲染" = 重新调用组件函数 ≠ 重新创建 DOM
   → 组件函数返回新的虚拟 DOM → diff → 只更新变了的真实 DOM 节点

❌ 误解 3："虚拟 DOM 是 React 发明的"
✅ 真相：虚拟 DOM 是一种模式，不是 React 独有的
   → Vue 2/3 也用虚拟 DOM
   → 但 Vue 结合了响应式系统，更精确地知道什么变了
   → Svelte 则完全不用虚拟 DOM（编译时确定更新路径）
```

---

## 5. 渲染流程全景

### 5.1 完整流程

```
这是 React 最核心的流程，后续所有阶段的知识都围绕它展开：

 ┌─────────────────────────────────────────────────────────────┐
 │                                                             │
 │   setState()                                                │
 │      ↓                                                      │
 │   ① 触发渲染（Trigger）                                      │
 │      → React 标记该组件需要重新渲染                            │
 │      ↓                                                      │
 │   ② 渲染阶段（Render Phase）                                 │
 │      → React 调用组件函数                                    │
 │      → 组件函数返回新的 JSX                                   │
 │      → JSX → 新的虚拟 DOM                                    │
 │      → 新旧虚拟 DOM 做 diff                                  │
 │      → 计算出最小变更集                                       │
 │      ⚠️ 这个阶段是纯计算，不会修改 DOM                         │
 │      ↓                                                      │
 │   ③ 提交阶段（Commit Phase）                                 │
 │      → 把变更应用到真实 DOM                                   │
 │      → 浏览器重新绘制                                        │
 │      → 用户看到更新                                          │
 │      ↓                                                      │
 │   ④ Effect 阶段                                              │
 │      → useEffect 回调在 DOM 更新后异步执行                     │
 │      → useLayoutEffect 回调在绘制前同步执行（少用）              │
 │                                                             │
 └─────────────────────────────────────────────────────────────┘
```

### 5.2 什么会触发渲染

```
组件在以下情况会重新渲染：

1. 自己的 state 变了    → setState() 
2. 父组件重新渲染了     → 即使 props 没变！（这是性能优化的重点）
3. Context value 变了   → 消费了该 Context 的组件

⚠️ Props 变化本身不直接触发渲染！
   是"父组件重新渲染"触发了子组件渲染，只是恰好 props 也可能变了
   即使 props 没变，子组件默认也会跟着渲染 → 阶段 7 会学如何优化这个
```

### 5.3 Render ≠ 更新 DOM

```
这是很多人搞混的关键点：

"重新渲染" = React 重新调用组件函数，生成新的虚拟 DOM
"更新 DOM" = React 把实际变化应用到浏览器页面上

可能的情况：
  ✅ 组件重新渲染了，虚拟 DOM 对比后发现有变化 → 更新真实 DOM
  ✅ 组件重新渲染了，虚拟 DOM 对比后发现没变化 → 什么都不做

所以"重新渲染"不等于性能问题：
  → 组件函数被调用了（有开销）
  → 但如果 diff 后没变化，DOM 不会被动（开销很小）
  → 只有当组件函数本身很昂贵时，才值得优化
```

### 5.4 和 React 各阶段知识的关系

```
这个渲染流程是贯穿全路线的主线：

  阶段 2：你会亲手触发 ①，写 JSX 就是在定义 ② 的输出
  阶段 3：useEffect 控制 ④ 的时机
         useRef 绕过 ② 直接保存值（不触发渲染）
  阶段 5：自定义 Hook 封装 ①②④ 的逻辑
  阶段 7：React.memo 跳过 ②
         useMemo 缓存 ② 中的计算
         useCallback 稳定 ② 中的函数引用
```

---

## 6. 单向数据流

### 6.1 什么是单向数据流

```
React 中数据只能从上往下流：

      App (state: { user, theme })
       ↓ props           ↓ props
    Header             Content
     ↓ props             ↓ props
   Avatar            ArticleList

  → 父组件通过 props 把数据传给子组件
  → 子组件不能直接修改父组件的数据
  → 子组件要"通知"父组件 → 通过回调函数
```

### 6.2 为什么是单向的

```
单向数据流的好处：

  ✅ 可预测：数据从哪来一目了然（看 props 就知道）
  ✅ 可调试：出 bug 时沿着数据流向上追踪就行
  ✅ 可维护：不会出现"不知道是谁改了这个值"

双向绑定（如 Vue 的 v-model）的好处：
  ✅ 写起来更简洁（一行搞定表单绑定）
  ⚠️ 但数据变更来源更多，复杂应用中追踪更难

React 的选择：宁可多写几行代码，也要保证数据流可追踪
```

### 6.3 子组件如何"向上通信"

```jsx
// 通过回调函数（callback props）：

// 父组件
function TodoApp() {
  const [todos, setTodos] = useState([])

  const handleAdd = (text) => {             // ← 定义操作
    setTodos([...todos, { id: Date.now(), text }])
  }

  return <TodoInput onAdd={handleAdd} />    // ← 把操作传下去
}

// 子组件
function TodoInput({ onAdd }) {
  const [text, setText] = useState('')

  return (
    <form onSubmit={e => { e.preventDefault(); onAdd(text); setText('') }}>
      <input value={text} onChange={e => setText(e.target.value)} />
      <button>添加</button>
    </form>
  )
  // 子组件调用 onAdd → 实际执行的是父组件的 setTodos → 父组件 state 变化 → 重新渲染
}

// 数据流向：
// 下行：App → TodoInput（通过 props 传 onAdd）
// 上行：TodoInput → App（通过调用 onAdd 回调）
```

---

## 7. 和 Vue 的对比

### 7.1 核心机制对比

| 维度 | React | Vue |
|------|-------|-----|
| **更新触发** | 手动 setState → 重新调用整个组件函数 | 自动 Proxy 拦截 → 精确知道哪个属性变了 |
| **更新粒度** | 组件级（整个函数重跑 → diff） | 属性级（只更新用到该属性的 DOM） |
| **模板/渲染** | JSX（就是 JS，完全的编程能力） | template（类 HTML，有专用语法 v-if/v-for） |
| **状态修改** | 不可变（必须创建新对象） | 可变（直接修改 `data.count++`） |
| **心智模型** | 函数式：每次渲染是独立快照 | 响应式：数据变了 UI 自动变 |
| **数据流** | 严格单向 | 单向 + v-model 双向语法糖 |

### 7.2 同一个功能的思维方式差异

```
场景：从 count=0 变到 count=1

Vue 的思维：
  1. count 被 Proxy 包裹
  2. 你写 count++ → Proxy 的 set 拦截到
  3. 通知：使用了 count 的 <p>{{ count }}</p>
  4. 精确更新这个 <p> 的文本节点
  → 你感觉：数据变了，UI 自动变了

React 的思维：
  1. 你调用 setCount(1)
  2. React 标记组件需要重新渲染
  3. 重新调用整个组件函数，count 变成 1
  4. 返回新 JSX → 新虚拟 DOM
  5. diff 发现 <p>0</p> → <p>1</p>
  6. 更新这个 <p> 的文本节点
  → 你感觉：我告诉 React 新状态，React 重新算 UI
```

### 7.3 各自的优势场景

```
React 更适合：
  - 复杂的条件渲染逻辑（JSX 就是 JS，想怎么写就怎么写）
  - 函数式编程偏好的团队
  - 需要高度可预测的数据流

Vue 更适合：
  - 模板密集型的应用（template 语法更贴近 HTML）
  - 快速原型开发（响应式 + v-model 省很多代码）
  - 更少的样板代码（不用 useState、不用不可变更新）

两者都能做任何项目，差异更多在开发体验和思维方式上。
```

---

## 8. 常见误解澄清

### 8.1 关于"重新渲染"

```
❌ "重新渲染很慢，要尽量避免"
✅ 重新渲染 = 调用一个 JS 函数，通常几毫秒
   → 只有当函数本身做了昂贵计算，或者导致了不必要的 DOM 更新时，才需要优化
   → 大多数时候 React 的 diff 已经帮你最小化了 DOM 操作

❌ "组件渲染了就一定更新了 DOM"
✅ 渲染 ≠ DOM 更新
   → 渲染 = 调用组件函数，生成新虚拟 DOM
   → DOM 更新只在 diff 发现变化时才发生

❌ "props 变了组件才渲染"
✅ 父组件渲染了，子组件就会渲染，不管 props 变没变
   → 这是 React 的默认行为
   → 用 React.memo 可以改变这个行为（阶段 7）
```

### 8.2 关于"虚拟 DOM"

```
❌ "虚拟 DOM = React"
✅ 虚拟 DOM 是一种技术，Vue 也用，React Native 也用
   → React 的核心不是虚拟 DOM，而是"UI = f(state)"的编程模型

❌ "虚拟 DOM 让 React 比 jQuery 快"
✅ 精确手写的 jQuery 代码可以比 React 快
   → React 的优势不在性能，在于开发效率和可维护性
   → 对于大多数应用，React 的性能完全够用
```

---

## 9. 面试常问

### Q1: React 的核心思想是什么？

**答**：
React 的核心思想是 **UI = f(state)**——声明式地描述 UI 应该长什么样，由框架负责将状态变化映射到 DOM 更新。开发者只需要管理状态，React 通过虚拟 DOM diff 自动计算最小变更，应用到真实 DOM。

### Q2: 虚拟 DOM 是什么？为什么需要它？

**答**：
- **是什么**：用 JS 对象描述 DOM 结构的一棵树。JSX 编译后就是 `React.createElement()` 调用，返回的就是虚拟 DOM 节点。
- **为什么需要**：React 采用声明式编程模型（你描述结果，不描述过程），需要一个"翻译层"把声明转换成具体的 DOM 命令。虚拟 DOM 就是这个翻译层——通过新旧虚拟 DOM 的 diff，算出最小变更集，再应用到真实 DOM。
- **不是为了快**：而是让声明式编程变得实用，用可接受的性能代价换来更好的开发体验。

### Q3: React 的 diff 算法怎么工作的？

**答**：
React 的 diff 不是通用的 O(n³) 树对比算法，而是基于两个假设做到 O(n)：
1. **不同类型的元素产生不同的树**：`<div>` 变成 `<span>`，直接销毁重建，不尝试复用
2. **key 标识同级元素**：通过 key 识别列表中元素的增删移动，避免不必要的销毁重建

这两个假设在实际应用中几乎总是成立的，所以 React 的 diff 既快又准确。

### Q4: React 和 Vue 的核心区别？

**答**：
- **更新机制**：React 是组件级重渲染 + diff（整个函数重跑），Vue 是响应式精确追踪（Proxy 拦截属性变化）
- **状态修改**：React 要求不可变更新（创建新对象），Vue 允许直接修改
- **模板**：React 用 JSX（就是 JS），Vue 用 template（类 HTML）
- **本质差异**：React 更函数式、更显式；Vue 更响应式、更隐式。各有适合的场景。

### Q5: 什么是单向数据流？为什么 React 选择它？

**答**：
- 数据只能从父组件通过 props 传给子组件，子组件不能直接修改父组件的数据
- 子组件要影响父组件，需要通过父组件传下来的回调函数
- React 选择单向数据流是为了**可预测性**——任何数据都可以追溯到来源，出 bug 时沿数据流向上追踪即可
- 代价是代码量稍多（比如需要手动实现"双向绑定"效果），但换来的是大型应用中更强的可维护性

---

## 10. 练习

```
理论理解：
  1. 用自己的话解释 UI = f(state)，举一个不用 React 的类比
  2. 画出 setState → 用户看到变化 的完整流程（触发 → 渲染 → 提交 → Effect）
  3. 解释为什么 React 要求 state 不可变更新（和"快照"有什么关系）
  4. 虚拟 DOM 的作用是什么？它是为了性能吗？

对比思考：
  5. 如果你用过 Vue，列出 3 个 React 和 Vue 在思维方式上的差异
  6. 为什么 React 选择"函数重跑"而不是"精确追踪"？各有什么优缺点？

上手验证：
  7. 用 create-react-app 或 Vite 创建一个项目，写一个简单的计数器
     → 在组件函数开头加 console.log，观察每次渲染时函数是否被调用
  8. 修改计数器：加一个子组件(显示 count*2)
     → 观察父组件渲染时子组件是否也渲染了
```

---

## 📖 推荐学习路径

1. 阅读 [react.dev - Thinking in React](https://react.dev/learn/thinking-in-react) 官方教程
2. 阅读 Dan Abramov 的 [React as a UI Runtime](https://overreacted.io/react-as-a-ui-runtime/)
3. 确保理解：UI = f(state)、虚拟 DOM 是"声明式的翻译层"、渲染 ≠ DOM 更新

> ⬅️ [返回路线概览](../react-learning-roadmap.md) | ➡️ [下一阶段：第一个完整组件](./02-first-component.md)
