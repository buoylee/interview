"""可选 ragas RAG 指标(faithfulness / answer_relevancy / context_precision / context_recall)。
需要 `uv sync --extra eval` 安装 ragas,且需真实 LLM/embedding(live)。未安装时抛清晰错误。"""


def ragas_available() -> bool:
    try:
        import ragas  # noqa: F401
        return True
    except ImportError:
        return False


def evaluate_ragas(samples: list[dict]):
    """samples: [{question, answer, contexts: list[str], ground_truth?}]。
    返回 ragas 评估结果。仅在安装了 [eval] extra + 配好 LLM key 时可用。"""
    if not ragas_available():
        raise RuntimeError("ragas 未安装。运行 `uv sync --extra eval` 后再用。")
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, faithfulness

    ds = Dataset.from_list(samples)
    return evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision])
