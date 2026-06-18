"""可插拔的 embedder。

两种模式，用环境变量 LAB_EMBEDDER 选择：
- bge      (默认): BAAI/bge-small-zh-v1.5，真实语义向量，需要 sentence-transformers。
- lexical        : 纯标准库的 TF-IDF 词法向量，零依赖，用于离线冒烟。

两种 embedder 都返回 list[list[float]]，统一用本文件的 cosine() 比较，
所以检索/评估代码完全不关心底层用了哪种向量。
"""

import math
import os
import re


def _tokens(text):
    """简单分词：ASCII 词 + 中文单字 + 中文相邻 bigram。

    对中文不做真正的分词（也不需要），单字 + bigram 已足够支撑词法匹配冒烟。
    """
    text = text.lower()
    toks = re.findall(r"[a-z0-9]+", text)
    cjk = re.findall(r"[一-鿿]", text)
    toks += cjk
    toks += [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    return toks


def cosine(a, b):
    s = da = db = 0.0
    for x, y in zip(a, b):
        s += x * y
        da += x * x
        db += y * y
    if da == 0.0 or db == 0.0:
        return 0.0
    return s / math.sqrt(da * db)


class LexicalEmbedder:
    """纯标准库 TF-IDF。在给定语料上 fit 出词表和 idf，encode 出稠密向量。"""

    def __init__(self, corpus_texts):
        df = {}
        for txt in corpus_texts:
            for w in set(_tokens(txt)):
                df[w] = df.get(w, 0) + 1
        self.vocab = {w: i for i, w in enumerate(df)}
        n = len(corpus_texts)
        self.idf = {w: math.log((1 + n) / (1 + df[w])) + 1.0 for w in df}

    def encode(self, texts):
        out = []
        for t in texts:
            v = [0.0] * len(self.vocab)
            for w in _tokens(t):
                j = self.vocab.get(w)
                if j is not None:
                    v[j] += self.idf.get(w, 0.0)
            out.append(v)
        return out


class BGEEmbedder:
    """BAAI/bge-small-zh-v1.5，归一化后的语义向量。"""

    def __init__(self, model_name="BAAI/bge-small-zh-v1.5"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def encode(self, texts):
        emb = self.model.encode(list(texts), normalize_embeddings=True)
        return [[float(x) for x in row] for row in emb]


def get_embedder(corpus_texts):
    """返回 (embedder, mode_name)。bge 不可用时自动退回 lexical。"""
    name = os.environ.get("LAB_EMBEDDER", "bge").lower()
    if name == "lexical":
        return LexicalEmbedder(corpus_texts), "lexical"
    try:
        return BGEEmbedder(), "bge"
    except Exception as e:  # 没装 sentence-transformers / 下载失败
        print(f"[warn] 无法加载 bge（{e}）；退回 lexical 模式（仅冒烟，数值非语义）。")
        return LexicalEmbedder(corpus_texts), "lexical"
