from mvp_agentic_rag.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_rewards_items_high_in_multiple_lists():
    dense = ["a", "b", "c"]
    sparse = ["b", "a", "d"]

    fused = reciprocal_rank_fusion([dense, sparse], k=60)
    order = [item for item, _ in fused]

    # a 和 b 都在两路靠前,应排在只出现一次的 c/d 之前
    assert set(order[:2]) == {"a", "b"}
    assert order[0] == "a" or order[0] == "b"


def test_rrf_single_list_preserves_order():
    fused = reciprocal_rank_fusion([["x", "y", "z"]], k=60)
    assert [item for item, _ in fused] == ["x", "y", "z"]
