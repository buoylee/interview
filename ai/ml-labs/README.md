# ML 动手训练 Labs

> 为面试补「能跑、能训出模型」的 runnable 作品。设计见 `docs/superpowers/specs/2026-06-17-ml-training-labs-design.md`。
> 全部在 Apple M4 / 16GB / MPS 上几分钟内可跑;离线、固定 seed。

## 怎么跑

```bash
# 在本目录(ai/ml-labs/)下
uv sync --group tabular          # 装某个 lab 需要的依赖组
uv run pytest interview/a3-house-price -v
uv run python interview/a3-house-price/train.py
```

依赖组:`tabular`(A3)、`nlp`(A2)、`gpt`(A1)、`vision`(B1)、`audio`(B2)。

## Track A —— 面试核心

| Lab | 一句话面试故事 | 状态 |
|---|---|---|
| [A3 房价回归](interview/a3-house-price/) | 讲透 train/val/test、过拟合、正则、RMSE vs MAE、数据泄漏 | ✅ |
| A2 意图识别 | embedding+轻分类器 vs 微调 DistilBERT,何时不该用 LLM | ⏳ |
| A1 tiny-GPT 从零 | 手写 attention,Mac 上训出会生成文字的 decoder-only | ⏳ |

## Track B —— Robotics / Embodied AI

见 [robotics/](robotics/) —— ⚠️ 非当前面试,长线兴趣。
