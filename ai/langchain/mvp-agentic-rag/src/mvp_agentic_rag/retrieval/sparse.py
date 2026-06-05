from mvp_agentic_rag.core.db import Database
from mvp_agentic_rag.retrieval.types import RetrievedChunk


class SparseRetriever:
    def __init__(self, db: Database, fts_config: str = "simple"):
        self.db = db
        self.fts_config = fts_config

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, doc_id, chunk_idx, content, metadata,
                       ts_rank(tsv, plainto_tsquery(%s, %s)) AS score
                FROM kb_chunks
                WHERE tsv @@ plainto_tsquery(%s, %s)
                ORDER BY score DESC
                LIMIT %s
                """,
                (self.fts_config, query, self.fts_config, query, top_k),
            ).fetchall()
        return [
            RetrievedChunk(
                id=r[0], doc_id=r[1], chunk_idx=r[2],
                content=r[3], metadata=r[4], score=float(r[5]),
            )
            for r in rows
        ]
