"""跑 baseline / small-to-big 各配置，打一张可对比的指标表。

用法:
  python run.py                      # 默认 bge 语义模式（需装依赖，会下载模型）
  LAB_EMBEDDER=lexical python run.py # 纯标准库冒烟，验证管线（数值非语义）
  LAB_K=3 python run.py              # 改 top-k

指标(纯检索层，不需要 LLM):
  Recall@k   : top-k 里是否命中「答案所在的那一段」
  MRR        : 命中段第一次出现位置的倒数（越靠前越高）
  完整%       : 命中那条结果是否覆盖了「答案所在的完整小节」(small-to-big 的胜负手)
  平均ctx字数 : top-k 返回文本的总字数（噪声/成本的代理指标）
"""

import os

from chunking import build_chunks
from corpus import DOCS
from embedder import get_embedder
from golden_set import GOLDEN
from retrievers import baseline_big, baseline_small, portable_small_to_big

K = int(os.environ.get("LAB_K", "5"))


def section_index(docs):
    idx = {}
    for doc in docs:
        for sec in doc["sections"]:
            idx[sec["section_id"]] = {"heading": sec["heading"], "paras": sec["paras"]}
    return idx


def covers(result_text, para_text):
    """结果文本是否包含某一段（用子串判断，对四种检索器统一适用）。"""
    return para_text in result_text


def evaluate(per_query_results, golden, secidx, k):
    n = len(golden)
    recall = mrr = comp = 0.0
    chars = 0
    for res, g in zip(per_query_results, golden):
        sec = secidx[g["section_id"]]
        gold_para = sec["paras"][g["para_idx"]]
        sec_paras = sec["paras"]
        texts = [c.text for c in res[:k]]

        hit_ranks = [i for i, t in enumerate(texts) if covers(t, gold_para)]
        if hit_ranks:
            recall += 1
            mrr += 1.0 / (hit_ranks[0] + 1)
            hit_text = texts[hit_ranks[0]]
            if all(covers(hit_text, p) for p in sec_paras):
                comp += 1
        chars += sum(len(t) for t in texts)
    return {
        "recall": recall / n,
        "mrr": mrr / n,
        "completeness": comp / n,
        "avg_chars": chars / n,
    }


def main():
    small, big, parent_of, _children = build_chunks(DOCS)
    big_by_id = {c.id: c for c in big}
    secidx = section_index(DOCS)
    queries = [g["query"] for g in GOLDEN]

    fit_texts = [c.text for c in small] + [c.text for c in big] + queries
    emb, mode = get_embedder(fit_texts)
    print(f"\n嵌入模式: {mode}   top-k={K}   查询数={len(GOLDEN)}\n")

    small_vecs = emb.encode([c.text for c in small])
    big_vecs = emb.encode([c.text for c in big])
    q_vecs = emb.encode(queries)

    configs = {}
    configs["baseline_small"] = [
        baseline_small(qv, small, small_vecs, K) for qv in q_vecs
    ]
    configs["baseline_big"] = [baseline_big(qv, big, big_vecs, K) for qv in q_vecs]
    configs["small_to_big (portable)"] = [
        portable_small_to_big(qv, small, small_vecs, big_by_id, parent_of, K)
        for qv in q_vecs
    ]

    if mode == "bge":
        try:
            from llamaindex_way import run_llamaindex

            configs["small_to_big (LlamaIndex)"] = run_llamaindex(DOCS, queries, K)
        except Exception as e:
            print(f"[note] LlamaIndex 路跳过（{e}）。装好依赖后会自动参与对比。\n")
    else:
        print("[note] lexical 模式下跳过 LlamaIndex 路（它需要 bge / sentence-transformers）。\n")

    rows = [(name, evaluate(res, GOLDEN, secidx, K)) for name, res in configs.items()]

    header = f"{'配置':<26}{'Recall@'+str(K):>10}{'MRR':>8}{'完整%':>9}{'平均ctx字数':>14}"
    print(header)
    print("-" * 64)
    for name, m in rows:
        print(
            f"{name:<26}{m['recall']*100:>9.0f}%{m['mrr']:>8.2f}"
            f"{m['completeness']*100:>8.0f}%{m['avg_chars']:>14.0f}"
        )

    print("\n怎么读这张表:")
    print("  • baseline_small : 检得准(Recall/MRR高), 但完整%低 —— 只给了答案那一段, 上下文不全")
    print("  • baseline_big   : 完整%高, 但平均ctx字数大 —— 噪声和成本都上去了")
    print("  • small_to_big   : Recall≈small, 完整%≈big, 字数居中 —— 小块检索 + 整节上下文, 两头都要到")
    print("  • portable 与 LlamaIndex 两行接近 —— 同一个策略, 框架不是魔法, 裸 Python 也能复现")


if __name__ == "__main__":
    main()
