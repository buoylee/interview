# Deep Learning Foundation Systematic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the old dense `02-deep-learning` entry into a clear gateway, and upgrade the Deep Learning foundation pages so learners can fill Transformer prerequisites smoothly without reading an overloaded legacy chapter.

**Architecture:** Preserve old dense material as legacy reference, but make the default path point to `foundations/deep-learning/`. Each foundation page should be independently readable, focused on one prerequisite, and explicitly connect back to the Transformer systematic module. This batch does not create interview notes; it only strengthens first-time learning.

**Tech Stack:** Markdown documentation, existing `ai/ml-to-llm-roadmap` layout, shell verification with `rg`, `git diff --check`, and a local Markdown link checker.

---

## File Structure

- Move: `ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md` -> `ai/ml-to-llm-roadmap/02-deep-learning/legacy/01-neural-network-basics-reference.md`
  - Responsibility: Preserve the old dense chapter as optional reference.

- Create: `ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md`
  - Responsibility: Become a short gateway that routes learners to the new foundation pages instead of forcing them through the old long chapter.

- Modify: `ai/ml-to-llm-roadmap/02-deep-learning/README.md`
  - Responsibility: Mark the old `02-deep-learning` directory as legacy/reference and point default learners to `foundations/deep-learning/`.

- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/README.md`
  - Responsibility: Provide the default Deep Learning补课 navigation and explain when to read each page.

- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/01-neuron-mlp-activation.md`
  - Responsibility: Explain neuron, linear layer, activation, and MLP as prerequisites for token vectors and Transformer FFN.

- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/02-backprop-gradient-problems.md`
  - Responsibility: Explain loss, gradients, backprop, gradient disappearance/explosion, and why Residual/Norm matter.

- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/03-normalization-residual-initialization.md`
  - Responsibility: Explain Residual, LayerNorm/RMSNorm, initialization, and Pre-Norm in the minimum depth needed for Transformer Block.

- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/04-ffn-gating-for-transformer.md`
  - Responsibility: Explain FFN, GELU, GLU/SwiGLU, and why the FFN is not secondary to Attention.

- Modify: `ai/ml-to-llm-roadmap.md`
  - Responsibility: Update the migration status to say Deep Learning补课 has been systematized as a foundation layer.

## Content Standard For Foundation Pages

Each foundation page should use this heading order:

```markdown
## 这篇解决什么问题
## 学前检查
## 一个真实问题
## 核心概念
## 最小心智模型
## 和 Transformer 的连接
## 常见误区
## 自测
## 回到主线
```

Rules:

- The page must not become a generic deep learning textbook chapter.
- Each page explains only the prerequisite it owns.
- Formulas are allowed, but every formula needs a short plain-language interpretation.
- Every page must link back to at least one relevant Transformer systematic lesson.
- Every page must include 3 to 5 self-check questions.

## Task 1: Reposition Old Deep Learning Entry As Gateway

**Files:**
- Move: `ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md` -> `ai/ml-to-llm-roadmap/02-deep-learning/legacy/01-neural-network-basics-reference.md`
- Create: `ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md`
- Modify: `ai/ml-to-llm-roadmap/02-deep-learning/README.md`

- [ ] **Step 1: Create legacy directory and move old dense chapter**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/02-deep-learning/legacy
git mv ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md ai/ml-to-llm-roadmap/02-deep-learning/legacy/01-neural-network-basics-reference.md
```

Expected:
- The old file is preserved under `legacy/`.
- Git tracks the move.

- [ ] **Step 2: Create the new gateway file**

Create `ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md` with this content:

```markdown
# 2.1 神经网络基础：新版阅读入口

> **定位**：这篇不再作为长篇教材入口。新版路线把神经网络基础拆成更小的 foundation 文档，方便你按 Transformer 主线遇到的问题补课。

## 为什么要改

旧版 `01-neural-network-basics.md` 把神经元、MLP、激活函数、反向传播、梯度问题、Normalization、Residual、初始化等内容放在同一篇里。第一次学习时很容易感觉概念连续出现，但没有足够时间消化。

新版默认读法是：先走 Transformer 主线，卡住哪个前置概念，再回到对应 foundation。

## 默认补课路径

| 你卡在哪里 | 读这篇 |
|------------|--------|
| 不理解神经元、线性层、MLP、激活函数 | [神经元、MLP 与激活函数](../foundations/deep-learning/01-neuron-mlp-activation.md) |
| 不理解 loss、梯度、反向传播、梯度消失/爆炸 | [反向传播、梯度消失与梯度爆炸](../foundations/deep-learning/02-backprop-gradient-problems.md) |
| 不理解 Residual、LayerNorm、RMSNorm、初始化 | [Normalization、Residual 与初始化](../foundations/deep-learning/03-normalization-residual-initialization.md) |
| 不理解 FFN、GELU、SwiGLU、门控 | [Transformer FFN、GELU 与 SwiGLU](../foundations/deep-learning/04-ffn-gating-for-transformer.md) |

## 建议读法

1. 先读 [Transformer 必要基础](../04-transformer-foundations/)。
2. 遇到不懂的前置概念，再回到本页选择对应 foundation。
3. 补完后回到原来的 Transformer 章节，不要在旧版深度学习目录里横向扩散。

## 旧版参考

旧版长文已经保留为参考资料：[legacy/01-neural-network-basics-reference.md](./legacy/01-neural-network-basics-reference.md)。

它适合在你已经读完新版 foundation 后，想查更完整的激活函数、BN/LN、Dropout、初始化和面试问法时使用；不建议作为第一次学习入口。

> ⬅️ [返回本阶段 README](./README.md)
```

- [ ] **Step 3: Rewrite `02-deep-learning/README.md` positioning**

Update the opening section so it clearly says this directory is legacy/reference, not the default systematic path. The top of the file should include:

```markdown
# 阶段 2：深度学习基础（旧版参考）

> **定位**：这个目录保留旧版深度学习材料，供查漏补缺和扩展阅读使用。新版系统学习默认不从这里顺序读，而是从 [Transformer 必要基础](../04-transformer-foundations/) 出发，按需回到 [Deep Learning 补课](../foundations/deep-learning/)。
>
> **为什么这样改**：原来的深度学习阶段把太多前置概念塞进同一条学习线，容易让只想补 LLM 底层的学习者感觉跳跃。新版把“第一次讲懂 Transformer”放在主线，把神经网络基础拆成小的 foundation。
```

Replace the old quick path block with:

````markdown
## 新版默认路径

```text
先读 Transformer 主线
  -> 卡在神经网络基础
  -> 回到 foundations/deep-learning 对应小节补课
  -> 补完回到原 Transformer 章节
```

默认入口：

- [Transformer 必要基础](../04-transformer-foundations/)
- [Deep Learning 补课](../foundations/deep-learning/)
- [新版神经网络基础入口](./01-neural-network-basics.md)
````

Keep the legacy file table, but rename the table heading to `## 旧版材料索引` and add a `说明` column if needed. Do not delete links to other old files.

- [ ] **Step 4: Verify gateway links and migration wording**

Run:

```bash
rg -n "旧版参考|新版默认路径|Deep Learning 补课|legacy/01-neural-network-basics-reference|不建议作为第一次学习入口" ai/ml-to-llm-roadmap/02-deep-learning/README.md ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md
git diff --check
```

Expected:
- `rg` returns matches in both files.
- `git diff --check` prints no output.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add ai/ml-to-llm-roadmap/02-deep-learning/README.md ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md ai/ml-to-llm-roadmap/02-deep-learning/legacy/01-neural-network-basics-reference.md
git commit -m "docs: route deep learning basics to foundations"
```

Expected:
- Commit succeeds.

## Task 2: Expand Neuron / MLP / Activation Foundation

**Files:**
- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/01-neuron-mlp-activation.md`

- [ ] **Step 1: Rewrite with standard foundation headings**

Update the page to use the foundation heading order from this plan.

Required content:

- `## 这篇解决什么问题`
  - Explain that this page only teaches linear layer, bias, activation, and MLP.
  - State that it unlocks token vectors and Transformer FFN.
- `## 学前检查`
  - Mention vectors are enough; no need to understand backprop yet.
  - Link to `../../04-transformer-foundations/02-token-to-vector.md` as the first mainline place where vectors appear.
- `## 一个真实问题`
  - Use an example like: a model receives a token vector; how does it turn that vector into a more useful representation?
- `## 核心概念`
  - Include subsections: `线性层`, `偏置`, `激活函数`, `MLP`.
  - Explain that multiple linear layers without activation collapse into one linear transform.
- `## 最小心智模型`
  - Include:

```text
输入向量 x
-> 线性层 Wx + b
-> 激活函数引入非线性
-> 多层堆叠成 MLP
```

- `## 和 Transformer 的连接`
  - Link to `../../04-transformer-foundations/05-transformer-block.md`.
  - Explain that Transformer FFN is a per-token MLP.
- `## 常见误区`
  - Include at least: activation is not decoration; MLP does not read other tokens; FFN and Attention solve different problems.
- `## 自测`
  - Include 4 questions covering linear layer, activation, why no activation collapses, and Transformer FFN.
- `## 回到主线`
  - Link back to `../../04-transformer-foundations/05-transformer-block.md` and `./04-ffn-gating-for-transformer.md`.

- [ ] **Step 2: Verify required concepts**

Run:

```bash
rg -n "这篇解决什么问题|学前检查|一个真实问题|线性层|偏置|激活函数|MLP|多层线性|Transformer FFN|自测|回到主线" ai/ml-to-llm-roadmap/foundations/deep-learning/01-neuron-mlp-activation.md
git diff --check
```

Expected:
- `rg` returns matches for all required concepts.
- `git diff --check` prints no output.

- [ ] **Step 3: Commit Task 2**

Run:

```bash
git add ai/ml-to-llm-roadmap/foundations/deep-learning/01-neuron-mlp-activation.md
git commit -m "docs: systematize neuron mlp foundation"
```

Expected:
- Commit succeeds.

## Task 3: Expand Backprop / Gradient Foundation

**Files:**
- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/02-backprop-gradient-problems.md`

- [ ] **Step 1: Rewrite with standard foundation headings**

Update the page to use the foundation heading order from this plan.

Required content:

- Explain `loss -> gradient -> optimizer update`.
- Include the update formula:

```text
theta_new = theta_old - learning_rate * gradient
```

- Clarify that the gradient points toward increasing loss, so gradient descent subtracts it.
- Explain backprop as gradient propagation through the computation graph, not running the model backward.
- Explain gradient disappearance/explosion with the idea of repeatedly multiplying through many layers.
- Explain why this matters for Transformer depth and why Residual/Norm help.
- Link to `../../04-transformer-foundations/05-transformer-block.md`.
- Include at least 4 self-check questions.

- [ ] **Step 2: Verify required concepts**

Run:

```bash
rg -n "loss|gradient|optimizer|theta_new|learning_rate|反向传播|梯度消失|梯度爆炸|Residual|Norm|Transformer Block|自测|回到主线" ai/ml-to-llm-roadmap/foundations/deep-learning/02-backprop-gradient-problems.md
git diff --check
```

Expected:
- `rg` returns matches for all required concepts.
- `git diff --check` prints no output.

- [ ] **Step 3: Commit Task 3**

Run:

```bash
git add ai/ml-to-llm-roadmap/foundations/deep-learning/02-backprop-gradient-problems.md
git commit -m "docs: systematize backprop gradient foundation"
```

Expected:
- Commit succeeds.

## Task 4: Expand Residual / Normalization / Initialization Foundation

**Files:**
- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/03-normalization-residual-initialization.md`

- [ ] **Step 1: Rewrite with standard foundation headings**

Update the page to use the foundation heading order from this plan.

Required content:

- Explain that deep networks need stable information flow and gradient flow.
- Explain Residual with:

```text
y = x + F(x)
```

- Explain LayerNorm as normalizing inside one token representation, not across the batch.
- Explain RMSNorm as a lighter variant that normalizes by root-mean-square and usually skips mean-centering.
- Explain initialization as controlling signal scale at the start of training and breaking symmetry.
- Explain Pre-Norm at the level needed for Transformer Block: normalization before Attention/FFN often stabilizes deep Transformers.
- Link to `../../04-transformer-foundations/05-transformer-block.md`.
- Include at least 4 self-check questions.

- [ ] **Step 2: Verify required concepts**

Run:

```bash
rg -n "Residual|y = x \\+ F\\(x\\)|LayerNorm|RMSNorm|初始化|打破对称|Pre-Norm|Attention/FFN|Transformer Block|自测|回到主线" ai/ml-to-llm-roadmap/foundations/deep-learning/03-normalization-residual-initialization.md
git diff --check
```

Expected:
- `rg` returns matches for all required concepts.
- `git diff --check` prints no output.

- [ ] **Step 3: Commit Task 4**

Run:

```bash
git add ai/ml-to-llm-roadmap/foundations/deep-learning/03-normalization-residual-initialization.md
git commit -m "docs: systematize residual norm foundation"
```

Expected:
- Commit succeeds.

## Task 5: Expand FFN / GELU / SwiGLU Foundation

**Files:**
- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/04-ffn-gating-for-transformer.md`

- [ ] **Step 1: Rewrite with standard foundation headings**

Update the page to use the foundation heading order from this plan.

Required content:

- Explain the division of labor:

```text
Attention = token 之间交换信息
FFN = 每个 token 独立加工信息
```

- Explain standard FFN:

```text
FFN(x) = W_down * activation(W_up * x)
```

- Explain GELU as smooth activation, not hard cutoff.
- Explain GLU/SwiGLU as information branch plus gate branch.
- Clarify that SwiGLU gate is continuous multiplication, not if/else and not necessarily limited to 0-1.
- Clarify `W_gate`, `W_up`, `W_down` are FFN projection matrices, not Attention K/V.
- Link to `../../04-transformer-foundations/05-transformer-block.md`.
- Include at least 4 self-check questions.

- [ ] **Step 2: Verify required concepts**

Run:

```bash
rg -n "Attention = token|FFN = 每个 token|W_down|GELU|GLU|SwiGLU|gate|连续|不是 Attention 里的 K/V|Transformer Block|自测|回到主线" ai/ml-to-llm-roadmap/foundations/deep-learning/04-ffn-gating-for-transformer.md
git diff --check
```

Expected:
- `rg` returns matches for all required concepts.
- `git diff --check` prints no output.

- [ ] **Step 3: Commit Task 5**

Run:

```bash
git add ai/ml-to-llm-roadmap/foundations/deep-learning/04-ffn-gating-for-transformer.md
git commit -m "docs: systematize transformer ffn foundation"
```

Expected:
- Commit succeeds.

## Task 6: Update Foundation Index And Main Roadmap Status

**Files:**
- Modify: `ai/ml-to-llm-roadmap/foundations/deep-learning/README.md`
- Modify: `ai/ml-to-llm-roadmap.md`

- [ ] **Step 1: Update foundation README**

Ensure `ai/ml-to-llm-roadmap/foundations/deep-learning/README.md` says:

- This is a补课 layer, not the first default route.
- The default path is Transformer mainline -> specific foundation page -> return to original lesson.
- The four pages are ordered by dependency:
  1. Neuron / MLP / activation
  2. Backprop / gradient problems
  3. Residual / Norm / initialization
  4. FFN / GELU / SwiGLU
- It links to `../../04-transformer-foundations/`.

- [ ] **Step 2: Update main roadmap status**

In `ai/ml-to-llm-roadmap.md`, update the `Deep Learning 补课` status row from `已创建` to:

```markdown
| Deep Learning 补课 | 支撑 Transformer 的神经网络基础 | [foundations/deep-learning](./ml-to-llm-roadmap/foundations/deep-learning/) | 已系统化 |
```

Also update `## 系统学习路径` item 3 so it says foundation files are now available for Deep Learning prerequisites:

```markdown
3. 缺基础时进入 `foundations/`；Deep Learning 前置知识已拆成小节，补完再回主线。
```

- [ ] **Step 3: Verify navigation status**

Run:

```bash
rg -n "补课 layer|Transformer mainline|已系统化|Deep Learning 前置知识已拆成小节|foundations/deep-learning" ai/ml-to-llm-roadmap/foundations/deep-learning/README.md ai/ml-to-llm-roadmap.md
git diff --check
```

Expected:
- `rg` returns matches for all navigation/status terms.
- `git diff --check` prints no output.

- [ ] **Step 4: Commit Task 6**

Run:

```bash
git add ai/ml-to-llm-roadmap/foundations/deep-learning/README.md ai/ml-to-llm-roadmap.md
git commit -m "docs: update deep learning foundation navigation"
```

Expected:
- Commit succeeds.

## Task 7: Final Validation

**Files:**
- Verify all files changed in Tasks 1-6.

- [ ] **Step 1: Run whitespace validation**

Run:

```bash
git diff --check HEAD~6..HEAD
```

Expected:
- No output.
- Exit code `0`.

- [ ] **Step 2: Run local Markdown link validation for changed files**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re
import sys

files = [
    Path("ai/ml-to-llm-roadmap.md"),
    Path("ai/ml-to-llm-roadmap/02-deep-learning/README.md"),
    Path("ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md"),
    Path("ai/ml-to-llm-roadmap/02-deep-learning/legacy/01-neural-network-basics-reference.md"),
    Path("ai/ml-to-llm-roadmap/foundations/deep-learning/README.md"),
    Path("ai/ml-to-llm-roadmap/foundations/deep-learning/01-neuron-mlp-activation.md"),
    Path("ai/ml-to-llm-roadmap/foundations/deep-learning/02-backprop-gradient-problems.md"),
    Path("ai/ml-to-llm-roadmap/foundations/deep-learning/03-normalization-residual-initialization.md"),
    Path("ai/ml-to-llm-roadmap/foundations/deep-learning/04-ffn-gating-for-transformer.md"),
]

errors = []
pattern = re.compile(r"\\[[^\\]]+\\]\\(([^)]+)\\)")

for file in files:
    if not file.exists():
        errors.append(f"missing changed file {file}")
        continue
    text = file.read_text(encoding="utf-8")
    for match in pattern.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "#")):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:
            continue
        resolved = (file.parent / path_part).resolve()
        if not resolved.exists():
            errors.append(f"{file}: missing link target {target}")

if errors:
    print("\\n".join(errors))
    sys.exit(1)

print(f"checked {len(files)} files, links ok")
PY
```

Expected:
- Output: `checked 9 files, links ok`
- Exit code `0`.

- [ ] **Step 3: Verify default route no longer sends learners into dense legacy chapter**

Run:

```bash
rg -n "不建议作为第一次学习入口|旧版长文已经保留|已系统化|Deep Learning 前置知识已拆成小节|先读 Transformer 主线" ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/02-deep-learning/README.md ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md ai/ml-to-llm-roadmap/foundations/deep-learning/README.md
```

Expected:
- Each phrase is present in the relevant navigation files.

- [ ] **Step 4: Confirm working tree cleanliness**

Run:

```bash
git status --short
```

Expected:
- No output.
