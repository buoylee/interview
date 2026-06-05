from mvp_agentic_rag.core.db import Database, to_vector_literal
from mvp_agentic_rag.retrieval.types import RetrievedChunk


class DenseRetriever:
    def __init__(self, db: Database, embeddings):
        self.db = db
        self.embeddings = embeddings

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        vec = to_vector_literal(self.embeddings.embed_query(query))
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, doc_id, chunk_idx, content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM kb_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vec, vec, top_k),
            ).fetchall()
        return [
            RetrievedChunk(
                id=r[0], doc_id=r[1], chunk_idx=r[2],
                content=r[3], metadata=r[4], score=float(r[5]),
            )
            for r in rows
        ]
