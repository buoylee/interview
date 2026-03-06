# async/await 执行顺序

## 核心规则

**`async` 函数不是一调用就异步，而是遇到 `await` 才让出执行权。在那之前，它跟普通函数一样同步执行。**

## 常见误区

❌ 以为 `await child()` 是"停在当前函数等 child 完成"
✅ 实际上是"先钻进 child 同步执行，child 再钻进更深层，直到某一层遇到真正的异步操作才让出"

`await` 不是墙，是**隧道**——会一直往下钻，直到撞到真正需要等待的东西。

## 嵌套 async 函数的执行顺序

```js
async function A() {
  console.log('A1')       // 同步
  await B()               // 先调用 B()，B 开始同步执行
  console.log('A4')
}

async function B() {
  console.log('B1')       // 同步（B 还没遇到自己的 await）
  await C()               // 先调用 C()，C 开始同步执行
  console.log('B3')
}

async function C() {
  console.log('C1')       // 同步（C 还没遇到自己的 await）
  await fetch('/api')     // C 的第一个 await → 让出！
  console.log('C2')
}

A()
console.log('外部')
```

输出：

```
A1
B1
C1
外部        ← C 让出后，主线程继续执行外部代码
C2          ← fetch 完成后恢复
B3
A4
```

**规则：一个函数从进入到它自己的第一个 `await`，都是同步的。不管嵌套多深，按这个规则逐层拆就行。**

## `await` 什么时候让出

`await` **永远会让出**，区别是让出多久：

```js
// 未完成的 Promise → 让出到 resolve（可能几毫秒到几秒）
await fetch('/api')

// 已完成的 Promise → 让出一个微任务周期（几乎立刻恢复）
await Promise.resolve(42)

// 非 Promise 值 → 等价于 await Promise.resolve(值)
await 42
```

## `await fn()` 的拆解

```js
await child()

// 等价于：
const promise = child()  // 第一步：同步调用 child，不让出
await promise            // 第二步：对返回的 Promise 让出
```

函数调用本身永远是同步的。`await` 只作用于表达式**求值后的结果**（即 Promise），不会影响求值过程。

## 实际应用：守卫模式

在并发控制中，利用"await 前同步执行"的特性做守卫：

```js
let startPromise = null

async function start() {
  // 守卫：如果已经在启动中，等它完成
  if (startPromise) {
    await startPromise
    return
  }

  // 赋值在 await 之前，同步执行，不可能被打断
  startPromise = doAsyncInit()     // 同步赋值
  const result = await startPromise // 这里才让出
  startPromise = null
}
```

**关键：守卫检查到赋值之间不能有 `await`，否则会被其他调用穿越。**
这在 JS 单线程模型下等价于 Java 中的"锁"——利用同步代码段不可被打断的特性实现互斥。

## 与 Python 的区别

| | JS | Python |
|---|---|---|
| 事件循环 | 内置（浏览器/Node） | 需要显式 `asyncio.run()` |
| await 的对象 | Promise | Coroutine / Awaitable |
| 不 await 的后果 | Promise 静默执行 | 协程**不会执行**，只是一个对象 |
