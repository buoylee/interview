import sys

from mvp_agentic_rag.core.config import get_settings
from mvp_agentic_rag.core.db import get_database
from mvp_agentic_rag.core.llm import get_embeddings
from mvp_agentic_rag.ingest.pipeline import IngestionPipeline


def main(argv: list[str]) -> int:
    if not argv:
        print("用法: python -m mvp_agentic_rag.ingest.cli <目录>")
        return 1
    directory = argv[0]
    s = get_settings()
    db = get_database()
    db.init_schema()
    pipe = IngestionPipeline(
        db=db,
        embeddings=get_embeddings(s),
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
    )
    n = pipe.ingest_directory(directory)
    print(f"已入库 {n} 个新片段(来自 {directory})")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
