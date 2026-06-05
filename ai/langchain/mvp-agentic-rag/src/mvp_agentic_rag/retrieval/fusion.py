from collections.abc import Hashable


def reciprocal_rank_fusion(
    rankings: list[list[Hashable]], k: int = 60
) -> list[tuple[Hashable, float]]:
    """对多路排名做 RRF 融合,返回按融合分降序的 (item, score)。"""
    scores: dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
