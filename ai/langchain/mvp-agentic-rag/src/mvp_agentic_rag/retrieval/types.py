from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    id: int
    doc_id: str
    chunk_idx: int
    content: str
    metadata: dict
    score: float = 0.0
