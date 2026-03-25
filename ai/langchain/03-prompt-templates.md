# 第1章：Prompt Templates — Prompt 工程化管理

> Prompt 是 LLM 应用的灵魂。LangChain 的 Prompt Template 让 Prompt 从硬编码字符串变成可复用、可组合、可版本管理的工程组件。

---

## 一、为什么需要 Prompt Template

### 1.1 硬编码 vs 模板化

```python
# ❌ 硬编码 — 不可复用，难以维护
response = llm.invoke(f"你是一个翻译专家，把以下内容翻译成{target_lang}：{text}")

# ✅ 模板化 — 可复用，可组合，可测试
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个翻译专家，只输出翻译结果"),
    ("human", "把以下内容翻译成{target_lang}：{text}"),
])
chain = prompt | llm
result = chain.invoke({"target_lang": "英文", "text": "我爱编程"})
```

### 1.2 核心价值

| 价值 | 说明 |
|------|------|
| **复用** | 一个模板用于多个场景，只需换变量 |
| **组合** | 多个模板可以用 LCEL 串联 |
| **类型安全** | 变量未填会报错，避免运行时问题 |
| **版本管理** | Prompt 可以像代码一样 git 管理 |
| **与 LCEL 集成** | 模板是 Runnable，支持 invoke/stream/batch |

---

## 二、ChatPromptTemplate — 核心类

### 2.1 基础用法

```python
from langchain_core.prompts import ChatPromptTemplate

# 方式1: from_messages() — 最常用
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个{role}，用{language}回答"),
    ("human", "{question}"),
])

# 查看模板的输入变量
print(prompt.input_variables)  # ['role', 'language', 'question']

# 格式化为消息列表
messages = prompt.invoke({
    "role": "Python 专家",
    "language": "中文",
    "question": "什么是装饰器?"
})
print(messages)
# ChatPromptValue(messages=[
#   SystemMessage(content='你是一个Python 专家，用中文回答'),
#   HumanMessage(content='什么是装饰器?')
# ])
```

```python
# 方式2: from_template() — 单消息模板
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_template(
    "解释{concept}，给{audience}听，用{language}"
)
# 默认生成 HumanMessage
```

### 2.2 消息角色类型

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "系统指令"),       # → SystemMessage
    ("human", "用户消息"),        # → HumanMessage  (等价于 "user")
    ("ai", "AI 回复"),           # → AIMessage     (等价于 "assistant")
    ("placeholder", "{history}"), # → 动态插入消息列表 (见下文)
])
```

### 2.3 面试高频问题

> **Q: ChatPromptTemplate.from_messages() 和 from_template() 有什么区别？**
>
> A: `from_messages()` 接收消息列表，支持多角色 (system/human/ai)，是**推荐方式**；`from_template()` 只创建单条消息 (默认 HumanMessage)，适合简单场景。实际项目中几乎总是用 `from_messages()`，因为你至少需要一条 SystemMessage 来约束模型行为。

---

## 三、动态消息 — MessagesPlaceholder

### 3.1 插入对话历史

对话系统中，需要把历史消息动态注入 Prompt。

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有帮助的助手"),
    MessagesPlaceholder("history"),  # 动态插入历史消息
    ("human", "{input}"),
])

# 使用时传入消息列表
from langchain.messages import HumanMessage, AIMessage

messages = prompt.invoke({
    "history": [
        HumanMessage(content="你好"),
        AIMessage(content="你好！有什么可以帮你的？"),
    ],
    "input": "你还记得我之前说了什么吗？"
})
```

### 3.2 简写方式 — placeholder

```python
# 等价写法, 更简洁
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有帮助的助手"),
    ("placeholder", "{history}"),    # 等价于 MessagesPlaceholder
    ("human", "{input}"),
])
```

### 3.3 可选的 Placeholder

```python
# 设置 optional=True, 没有传入时不报错
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个助手"),
    MessagesPlaceholder("history", optional=True),  # 可选
    ("human", "{input}"),
])

# 不传 history 也不会报错
messages = prompt.invoke({"input": "hello"})
```

### 3.4 面试深度问题

> **Q: MessagesPlaceholder 和普通字符串变量有什么区别？**
>
> A: 普通变量 `{var}` 插入的是**字符串**，会被格式化进某条消息的 content 中；`MessagesPlaceholder` 插入的是**消息对象列表**，每个元素都是完整的 Message (有 role 和 content)。这对保持正确的对话格式至关重要——如果你把历史消息拼成字符串放进一条 HumanMessage，LLM 会分不清谁说了什么。

---

## 四、Few-Shot Prompting — 少样本学习

### 4.1 静态 Few-Shot

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个情感分析专家，输出：积极/消极/中立"),
    # Few-shot 示例
    ("human", "这个产品太好用了！"),
    ("ai", "积极"),
    ("human", "快递速度很慢，包装也破了"),
    ("ai", "消极"),
    ("human", "还行吧，一般般"),
    ("ai", "中立"),
    # 实际输入
    ("human", "{text}"),
])

chain = prompt | llm
result = chain.invoke({"text": "这款手机性价比很高，推荐购买"})
```

### 4.2 动态 Few-Shot

当示例很多时，动态选择最相关的示例。

```python
from langchain_core.prompts import FewShotChatMessagePromptTemplate, ChatPromptTemplate

# 定义示例
examples = [
    {"input": "太棒了", "output": "积极"},
    {"input": "很差劲", "output": "消极"},
    {"input": "还可以", "output": "中立"},
    {"input": "非常喜欢", "output": "积极"},
    {"input": "不推荐", "output": "消极"},
]

# 单个示例的模板
example_prompt = ChatPromptTemplate.from_messages([
    ("human", "{input}"),
    ("ai", "{output}"),
])

# 组合 Few-Shot 模板
few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=example_prompt,
    examples=examples,
)

# 完整 Prompt
final_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个情感分析专家"),
    few_shot_prompt,
    ("human", "{text}"),
])
```

### 4.3 基于向量相似度的动态示例选择

```python
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# 用向量相似度选择最相关的示例
selector = SemanticSimilarityExampleSelector.from_examples(
    examples,
    OpenAIEmbeddings(),
    Chroma,
    k=2,  # 选最相关的 2 个
)

few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=example_prompt,
    example_selector=selector,  # 用 selector 替代 examples
)
```

### 4.4 面试加分点

> **Q: 什么时候用 Few-Shot，什么时候用 Fine-tuning？**
>
> A: **Few-Shot** 适合：任务简单、数据少 (<20 个示例)、需要快速迭代、不想承担微调成本。**Fine-tuning** 适合：任务复杂、数据多 (>100 个)、需要稳定高质量输出、对延迟敏感 (fine-tuned 模型不需要在每次请求中发送示例，节省 token)。实际项目中，先用 Few-Shot 验证可行性，效果不够再考虑 Fine-tuning。

---

## 五、高级模板技巧

### 5.1 Partial — 预填充部分变量

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{company}的客服，用{language}回答"),
    ("human", "{question}"),
])

# 预填充 company 和 language
partial_prompt = prompt.partial(company="鹅厂", language="中文")

# 使用时只需传 question
messages = partial_prompt.invoke({"question": "退货政策是什么？"})
```

**适用场景**：一个基础模板被多个场景共用，每个场景只需要覆盖部分变量。

### 5.2 用函数动态生成变量

```python
from datetime import datetime

def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

prompt = ChatPromptTemplate.from_messages([
    ("system", "当前时间是 {time}。你是一个助手。"),
    ("human", "{input}"),
])

# 用函数生成 time 变量
partial_prompt = prompt.partial(time=get_current_time)
```

### 5.3 嵌套模板组合

```python
# 定义子模板
system_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{role}，专长是{expertise}"),
])

chat_prompt = ChatPromptTemplate.from_messages([
    *system_prompt.messages,  # 展开子模板
    MessagesPlaceholder("history", optional=True),
    ("human", "{input}"),
])
```

---

## 六、常见 Prompt 设计模式 (面试必备)

### 6.1 角色扮演模式

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一位资深 {role}，拥有 10 年经验。
你的回答风格：
- 专业但易懂
- 给出具体示例
- 指出常见陷阱
不确定的内容请明确说明。"""),
    ("placeholder", "{history}"),
    ("human", "{input}"),
])
```

### 6.2 格式约束模式

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", """分析用户的输入，严格按以下 JSON 格式输出：
{{
    "sentiment": "积极|消极|中立",
    "confidence": 0.0-1.0,
    "key_phrases": ["短语1", "短语2"],
    "summary": "一句话总结"
}}
只输出 JSON，不要输出其他任何内容。"""),
    ("human", "{text}"),
])
```

> 注意：模板中的 `{` 和 `}` 需要用 `{{` 和 `}}` 转义，避免被当作变量。

### 6.3 思维链 (Chain-of-Thought) 模式

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个逻辑推理专家。
对每个问题：
1. 先分析问题的关键信息
2. 列出推理步骤
3. 给出最终答案

示例：
问题: 小明有5个苹果，给了小红2个，又买了3个，现在有多少？
分析: 需要计算苹果的数量变化
步骤: 5 - 2 + 3 = 6
答案: 6个"""),
    ("human", "{question}"),
])
```

### 6.4 面试总结

> **Q: 设计一个好的 System Prompt 有哪些原则？**
>
> A: (1) **角色定义** — 清晰说明 AI 是谁、专长什么；(2) **行为约束** — 规定输出格式、语言、风格；(3) **边界声明** — 说明不确定时怎么办、什么不应该做；(4) **示例** — 给 1-2 个输入输出示例；(5) **简洁** — 避免冗长指令，核心规则 5-7 条为宜。过长的 System Prompt 反而会让模型 "迷失"。

---

## 七、Prompt 与 LCEL 的集成

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Prompt 是 Runnable, 可以用 | 串联
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个翻译助手"),
    ("human", "翻译成{lang}: {text}"),
])

chain = prompt | ChatOpenAI() | StrOutputParser()
result = chain.invoke({"lang": "英文", "text": "我爱编程"})
# "I love programming"
```

---

## 八、练习任务

### 基础练习
- [ ] 创建一个带 system + human 的 ChatPromptTemplate
- [ ] 用 MessagesPlaceholder 实现多轮对话模板
- [ ] 用 partial() 预填充公司名称和语言

### 进阶练习
- [ ] 实现一个动态 Few-Shot Prompt (3 个示例)
- [ ] 结合向量相似度选择最相关的 Few-Shot 示例
- [ ] 设计一个 Chain-of-Thought Prompt 并测试效果

### 面试模拟
- [ ] 解释 ChatPromptTemplate 的工作原理
- [ ] 比较 MessagesPlaceholder 和字符串变量的区别
- [ ] 描述 Few-Shot vs Fine-tuning 的选择标准
- [ ] 说明设计好的 System Prompt 的原则

---

> **本章掌握后，你应该能**：设计结构化的 Prompt 模板，管理对话历史，实现 Few-Shot 学习，并知道常见的 Prompt 设计模式。
