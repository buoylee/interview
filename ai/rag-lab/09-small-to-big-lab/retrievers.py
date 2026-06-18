"""三个不依赖任何框架的检索器（裸 Python + cosine）。

- baseline_small : 在小块上检索，直接返回小块。     检得准，但上下文不全。
- baseline_big   : 在大块上检索，返回整节。         上下文全，但噪声/成本高。
- portable_small_to_big : 在小块上检索，命中后按阈值「上卷」到父节。

portable_small_to_big 就是 LlamaIndex AutoMergingRetriever 的手写等价物：
  在候选池里数一个父节下有几个子块被命中；够 merge_min 个就把整节还回去，
  否则只还命中的小块。一共三十来行，没有魔法。
"""

from embedder import cosine


def _rank(query_vec, chunks, chunk_vecs):
    scored = sorted(
        zip(chunks, chunk_vecs),
        key=lambda cv: cosine(query_vec, cv[1]),
        reverse=True,
    )
    return [c for c, _ in scored]


def baseline_small(query_vec, small, small_vecs, k):
    return _rank(query_vec, small, small_vecs)[:k]


def baseline_big(query_vec, big, big_vecs, k):
    return _rank(query_vec, big, big_vecs)[:k]


def portable_small_to_big(
    query_vec, small, small_vecs, big_by_id, parent_of, k, merge_min=2, pool_mult=3
):
    ranked = _rank(query_vec, small, small_vecs)
    pool = ranked[: k * pool_mult]

    # 数每个父节在候选池里命中了几个子块
    hits_per_parent = {}
    for c in pool:
        pid = parent_of[c.id]
        hits_per_parent[pid] = hits_per_parent.get(pid, 0) + 1

    out, used_parents = [], set()
    for c in ranked:
        pid = parent_of[c.id]
        if hits_per_parent.get(pid, 0) >= merge_min:
            # 同节命中够多 → 上卷返回整节（去重）
            if pid in used_parents:
                continue
            used_parents.add(pid)
            out.append(big_by_id[pid])
        else:
            # 只命中孤立的一段 → 就还这一小块
            out.append(c)
        if len(out) >= k:
            break
    return out
