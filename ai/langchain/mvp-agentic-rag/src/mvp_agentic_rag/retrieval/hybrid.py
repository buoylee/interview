from mvp_agentic_rag.retrieval.dense import DenseRetriever
from mvp_agentic_rag.retrieval.fusion import reciprocal_rank_fusion
from mvp_agentic_rag.retrieval.rerank import Reranker
from mvp_agentic_rag.retrieval.sparse import SparseRetriever
from mvp_agentic_rag.retrieval.types import RetrievedChunk


class HybridRetriever:
    def __init__(
        self,
        dense: DenseRetriever,
        sparse: SparseRetriever,
        reranker: Reranker,
        top_k_dense: int,
        top_k_sparse: int,
        rrf_k: int,
        rerank_top_n: int,
    ):
        self.dense = dense
        self.sparse = sparse
        self.reranker = reranker
        self.top_k_dense = top_k_dense
        self.top_k_sparse = top_k_sparse
        self.rrf_k = rrf_k
        self.rerank_top_n = rerank_top_n

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        dense_hits = self.dense.search(query, self.top_k_dense)
        sparse_hits = self.sparse.search(query, self.top_k_sparse)

        by_id: dict[int, RetrievedChunk] = {}
        for hit in [*dense_hits, *sparse_hits]:
            by_id.setdefault(hit.id, hit)

        fused = reciprocal_rank_fusion(
            [[h.id for h in dense_hits], [h.id for h in sparse_hits]],
            k=self.rrf_k,
        )
        # Map fused ids back to chunks; skip any id not present in by_id
        candidate_ids = [item_id for item_id, _ in fused]
        candidates = [by_id[i] for i in candidate_ids if i in by_id]

        return self.reranker.rerank(query, candidates, self.rerank_top_n)
