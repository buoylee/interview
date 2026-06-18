"""把语料切成小块(段落)和大块(整节)，并记录父子关系。

这一层故意做得很笨：小块 = 段落，大块 = 整节，parent_of 把小块指回它的节。
真实系统里 chunk 边界会更复杂，但 small-to-big 的本质就这么点东西。
"""

from dataclasses import dataclass


@dataclass
class Chunk:
    id: str
    text: str
    doc_id: str
    section_id: str
    kind: str  # 'small'(段落) | 'big'(整节)


def build_chunks(docs):
    """返回 (small_chunks, big_chunks, parent_of, children_of)。

    - small_chunks: 每个段落一个
    - big_chunks  : 每个 section 一个（heading + 全部段落拼起来）
    - parent_of   : small.id -> big.id
    - children_of : big.id   -> [small.id, ...]
    """
    small, big = [], []
    parent_of, children_of = {}, {}
    for doc in docs:
        for sec in doc["sections"]:
            sec_id = sec["section_id"]
            big_id = f"BIG::{sec_id}"
            sec_text = sec["heading"] + "\n" + "\n".join(sec["paras"])
            big.append(Chunk(big_id, sec_text, doc["doc_id"], sec_id, "big"))
            children_of[big_id] = []
            for i, para in enumerate(sec["paras"]):
                sid = f"SMALL::{sec_id}.{i}"
                small.append(Chunk(sid, para, doc["doc_id"], sec_id, "small"))
                parent_of[sid] = big_id
                children_of[big_id].append(sid)
    return small, big, parent_of, children_of
