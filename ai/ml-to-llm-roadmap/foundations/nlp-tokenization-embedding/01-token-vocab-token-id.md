# Token、Vocab 与 Token ID

## 这篇解决什么卡点

读到 Transformer 的“文本先变成 token id，再查表变成向量”时，最常见的卡点是：为什么一句话不能直接按字或词送进去，为什么还要多出 token、vocab、token id 这几层。

这里先解决这个卡点：Transformer 看到的不是原始文字，而是一串模型可识别的文本单位编号。

## 先记住一句话

token 是模型侧的文本单位，vocab 是模型允许使用的 token 清单，token id 是 token 在这个清单里的整数编号。

token 不一定等于一个词。它可能是一个词、一个词片段、一个标点、一个空格相关片段，或者代码里的某段字符。

## 最小例子

```text
"unhappy" 可能被切成 ["un", "happy"]
"user_id" 在代码或 JSON 里也会被拆成多个 token
```

如果 vocab 里有：

| token | token id |
|-------|----------|
| `un` | 501 |
| `happy` | 902 |
| `_` | 17 |
| `id` | 314 |

那么 token id 只是编号标签。`314` 本身不表示“身份”或“变量名”，它只表示“去 vocab 里找第 314 个 token”。

## 为什么 unhappy 会被切成 un + happy

这一步最容易误会成“因为 un- 是个前缀，所以按词根切”。不是的。切分跟语法词根没关系，只跟 vocab 里有没有这个片段有关系。

原因要从一个硬约束说起：vocab 是**固定大小**的清单（常见是几万到十几万个 token）。但要表示的文本是无穷的——英文新词、各种语言、代码标识符、错拼、表情符号——不可能每个词都单独占一个 id。

既然装不下所有词，vocab 就只装“高频、可复用的片段”。`un`、`happy`、`ing`、`ed` 这类片段在成千上万个词里反复出现，给它们各自一个 id 非常划算：少数几个片段就能拼出大量的词。

`unhappy` 作为一个整体，出现频率没高到值得单独占一个 id，所以 vocab 里大概率**没有** `unhappy` 这个 token。

于是 tokenizer 遇到 `unhappy` 时只能退一步：用它认识的、能覆盖这串字符的片段去拼。它手里正好有 `un` 和 `happy`，接起来恰好等于 `unhappy`，于是切成 `["un", "happy"]`。

一句话总结：切分是按“用尽量少的已知片段拼出这串字符”来切的，不是按语法切的。`un-` 在这里碰巧是前缀，纯属巧合——比如 `tokenization` 常被切成 `["token", "ization"]`，而不是语法上的 `token` + `ize` + `ation`。

这也正好回答了开头的卡点：为什么不能直接按词送进去？因为固定大小的 vocab 装不下所有词；用可复用的子词片段，有限的 vocab 才能表示几乎无限的文本，包括从没见过的词。

## 这是人切的，还是自动切的

不是人切的。没有人去规定“unhappy 要切成 un + happy”。关键是把两件事分开看：

**① 造 vocab（训练 tokenizer，只做一次）**

喂进一大堆语料，用统计的办法自动找出“哪些片段值得当 token”。最经典的做法（BPE）是：一开始每个字符各算一个 token，然后反复把“语料里相邻出现最频繁的一对”合并成一个新 token，并记下这条合并规则，直到 vocab 凑够预定大小。`un`、`happy` 能进 vocab，是因为它们高频、被自动合并出来的，不是人挑的。这一步产出两样东西：一张 vocab 表，和一串**有先后顺序**的合并规则。

**② 用 vocab 切词（每次编码文本都做）**

拿到 `unhappy`，先打散成单个字符，再按第 ① 步学到的合并规则、照顺序往回拼：能合的相邻对就合，直到没得合。结果就是 `un` + `happy`。这一步是确定性的，同样的输入永远切出同样的结果。

给后端的类比：很像**编译期生成一张映射表、运行期查表套规则**。训练 tokenizer = 扫一遍数据、按频率建表（跟哈夫曼编码、字典压缩建表是一个味道）；编码文本 = 拿现成的表机械地套，不再重新统计。

人唯一定的是“规则框架”：vocab 多大、基本单位是字节还是字符、要不要先按空格切一刀、有哪些特殊 token。具体某个词怎么切，是数据和频率决定的，不是人手定的。

合并规则到底怎么一步步学出来（BPE、WordPiece、SentencePiece 的差别），属于算法细节，需要时看 [旧版 Tokenization 深入](../../03-nlp-embedding-retrieval/06-tokenization-deep-dive.md)。

## 每个 model 都有自己的 tokenizer 吗

准确说法：不是“每个 model 都新训一个独一无二的 tokenizer”，但**每个 model 都绑定、且只绑定一个 tokenizer**。模型和它的 tokenizer 是焊死的一对。

为什么焊死：模型的 embedding 表有 `vocab_size` 行，“token id 对应第几行”是训练时连同权重一起学死的。换一个 tokenizer，id 就对不上行，查出来的向量全乱——相当于模型是按某个 enum 编译出来的，你给它换了个 enum，序号 `314` 的含义就变了。所以**不能把一个 model 的 token id 喂给另一个 model**。

但 tokenizer 经常被复用，所以不是“一个模型一个”：

- 同一家族共用一套。比如 GPT-3.5 和 GPT-4 共用约 10 万的词表，GPT-4o 换成约 20 万；Llama 2 用 3.2 万的词表，Llama 3 换成 12.8 万。
- 也常直接借现成的，而不是重训。

什么时候才会新训一个：换代、要覆盖新语言或代码、或想要不一样的 vocab 大小。

对你实际意味着：**同一句话在不同 model 下 token 数不一样**。所以算上下文长度、算调用费用时，要用对应 model 的 tokenizer 去数，不能拿这个模型的数字套到那个模型上。

那能不能拿到这些 tokenizer 自己数？要看是谁家的：

- **OpenAI：公开。** 它的分词器是开源库 `tiktoken`，词表加合并规则都能下载，**本地离线**就能数 token、还原切分。
- **Anthropic（Claude）：不公开。** 至少 Claude 3 及以后没有可下载的官方 tokenizer，要准确数 token 只能调官方的 `count_tokens` API（服务端帮你数，要联网）。

一个常见的坑：**别拿 `tiktoken` 去数 Claude 的 token**。那是 OpenAI 的分词器，对 Claude 会数错（一般少算 15%~20%，代码和非英文更多）。道理还是那句——tokenizer 和 model 是绑定的，用错 tokenizer，数出来的就是错的。

## 这个概念在 Transformer 哪里出现

主线的 [从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md) 里，第一步就是把文本切成 token，再把 token 映射成 token id。

Transformer 后面的 attention、MLP、layer norm 都不直接处理文字。它们处理的是由 token id 查表得到的向量。

## 和旧资料的连接

这里不展开 tokenizer 的算法细节，也不比较 BPE、WordPiece、SentencePiece。只要先记住：token 是模型输入单位，token id 是查表用的整数索引。

需要深入时再读 [旧版 Tokenization 深入](../../03-nlp-embedding-retrieval/06-tokenization-deep-dive.md)。

## 自测

1. token 为什么不一定等于词？
2. vocab 和 token id 的关系是什么？
3. 为什么 token id 本身没有语义？
4. 为什么 `unhappy` 会被切成 `un` + `happy`，而不是保留成一个整 token？
5. 切分是人手定的还是自动的？分成哪两个阶段（造 vocab、用 vocab）？
6. 为什么不能把一个 model 的 token id 喂给另一个 model？

## 回到主线

回到 [从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md)，继续看 token id 如何进入 embedding table。
