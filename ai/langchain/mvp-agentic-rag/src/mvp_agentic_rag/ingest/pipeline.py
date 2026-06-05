import hashlib

from psycopg.types.json import Jsonb

from mvp_agentic_rag.core.db import Database, to_vector_literal
from mvp_agentic_rag.ingest.loader import load_documents
from mvp_agentic_rag.ingest.splitter import split_text


class IngestionPipeline:
    def __init__(self, db: Database, embeddings, chunk_size: int, chunk_overlap: int):
        self.db = db
        self.embeddings = embeddings
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def ingest_directory(self, directory: str) -> int:
        docs = load_documents(directory)
        rows: list[tuple] = []
        for doc in docs:
            chunks = split_text(doc["text"], self.chunk_size, self.chunk_overlap)
            if not chunks:
                continue
            vectors = self.embeddings.embed_documents(chunks)
            for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                content_hash = hashlib.sha256(
                    f"{doc['doc_id']}::{idx}::{chunk}".encode()
                ).hexdigest()
                rows.append(
                    (
                        doc["doc_id"],
                        idx,
                        chunk,
                        content_hash,
                        Jsonb({"doc_id": doc["doc_id"], "chunk_idx": idx}),
                        to_vector_literal(vec),
                    )
                )

        inserted = 0
        with self.db.connect() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO kb_chunks
                            (doc_id, chunk_idx, content, content_hash, metadata, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s::vector)
                        ON CONFLICT (content_hash) DO NOTHING
                        """,
                        row,
                    )
                    inserted += cur.rowcount
            conn.commit()
        return inserted
