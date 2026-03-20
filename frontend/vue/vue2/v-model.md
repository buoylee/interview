[toc]

## v-model 本质

`v-model` 是语法糖，在不同场景下展开方式不同：

### 原生元素上

```html
<input v-model="msg">
<!-- 等价于 -->
<input :value="msg" @input="msg = $event.target.value">
```

### 组件上

```html
<MyComp v-model="msg">
<!-- 等价于 -->
<MyComp :value="msg" @input="msg = $event">
```

所以一个组件要支持 `v-model`，必须：
1. 接收 `value` prop
2. 变更时 `$emit('input', newVal)`



## input 与 change 的区别

### 原生 DOM 层面

| 事件    | 触发时机                   |
| ------- | -------------------------- |
| `input` | 每次值变化（实时，包括输入中） |
| `change`| 失焦或回车确认时            |

### Vue 组件层面

| 事件    | 含义                                 |
| ------- | ------------------------------------ |
| `input` | **Vue 框架约定**，驱动 `v-model` 双向绑定 |
| `change`| **组件自己提供的业务事件**，语义更明确    |

以 Element UI 的 `el-checkbox-group` 为例，内部触发顺序：

```js
// Element UI 源码简化
handleChange(val) {
  this.$emit('input', val)   // 1. 先更新 v-model
  this.$emit('change', val)  // 2. 再通知业务
}
```

两者参数一样，区别仅在于 `input` 是 v-model 机制必需的，`change` 是额外提供的。



## 拆写 v-model（避免 mutating props）

直接 `v-model="item.answers"` 会触发 ESLint `vue/no-mutating-props` 报错。

拆开写法：

```html
<!-- 拆开 v-model -->
<el-checkbox-group :value="item.answers" @input="onAnswersChange">

<script>
methods: {
  onAnswersChange(val) {
    this.$set(this.item, 'answers', val)
  }
}
</script>
```

- `:value` — 单向传入当前值
- `@input` — 监听变更，手动更新
- `$set` — 保证 Vue 2 响应式追踪到变化



## :model-value 是 Vue 3 的写法

Vue 3 改了 v-model 的约定：

| | Vue 2 | Vue 3 |
|---|---|---|
| prop 名 | `value` | `modelValue` |
| 事件名 | `input` | `update:modelValue` |
| 模板绑定 | `:value` + `@input` | `:model-value` + `@update:model-value` |

**在 Vue 2 项目中写 `:model-value` 不会生效**，组件不认识这个 prop。
