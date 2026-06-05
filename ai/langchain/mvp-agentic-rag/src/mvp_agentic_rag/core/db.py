import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from mvp_agentic_rag.core.config import get_settings


class Database:
    def __init__(self, conninfo: str, embed_dim: int):
        self.conninfo = conninfo
        self.embed_dim = embed_dim
        self._ensure_extension()
        self.pool = ConnectionPool(
            conninfo,
            min_size=1,
            max_size=5,
            configure=self._configure,
            open=True,
        )

    def _ensure_extension(self) -> None:
        with psycopg.connect(self.conninfo) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()

    @staticmethod
    def _configure(conn: psycopg.Connection) -> None:
        register_vector(conn)

    def connect(self):
        return self.pool.connection()

    def init_schema(self) -> None:
        ddl = f"""
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS kb_chunks (
            id           BIGSERIAL PRIMARY KEY,
            doc_id       TEXT NOT NULL,
            chunk_idx    INT  NOT NULL,
            content      TEXT NOT NULL,
            content_hash TEXT NOT NULL UNIQUE,
            metadata     JSONB NOT NULL DEFAULT '{{}}',
            embedding    vector({self.embed_dim}) NOT NULL,
            tsv          tsvector GENERATED ALWAYS AS
                         (to_tsvector('simple', content)) STORED
        );
        CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx
            ON kb_chunks USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS kb_chunks_tsv_idx
            ON kb_chunks USING GIN (tsv);
        """
        with self.connect() as conn:
            # ddl 仅插值 self.embed_dim(来自校验过的 Settings 的 int,非用户输入),
            # 无注入风险;f-string 是 str 而非 LiteralString,故显式忽略类型告警。
            conn.execute(ddl)  # type: ignore[arg-type]
            conn.commit()

    def close(self) -> None:
        self.pool.close()


def to_vector_literal(vec) -> str:
    """把向量序列化成 pgvector 文本字面量 '[1.0,2.0,...]',配 %s::vector 使用。
    用字面量 + 显式 cast,避开不同版本 pgvector 适配器对 list 支持的差异。"""
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def get_database() -> Database:
    s = get_settings()
    return Database(s.database_url, s.embed_dim)


if __name__ == "__main__":
    db = get_database()
    db.init_schema()
    print("schema initialized")
