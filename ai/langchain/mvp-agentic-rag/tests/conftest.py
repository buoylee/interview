import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from testcontainers.postgres import PostgresContainer

EMBED_DIM = 64  # 测试用小维度,加速


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer(
        "pgvector/pgvector:pg16",
        username="rag",
        password="rag",
        dbname="rag",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def conninfo(pg_container):
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql://rag:rag@{host}:{port}/rag"


@pytest.fixture
def fake_embeddings():
    return DeterministicFakeEmbedding(size=EMBED_DIM)


@pytest.fixture
def clean_db(conninfo):
    """每个测试前重建 schema,保证隔离。"""
    from mvp_agentic_rag.core.db import Database

    db = Database(conninfo, embed_dim=EMBED_DIM)
    with db.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS kb_chunks")
        conn.commit()
    db.init_schema()
    yield db
    db.close()
