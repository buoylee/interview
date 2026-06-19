# python-data lab

用**真实 Postgres** 复现数据访问的四个核心现象——连接池耗尽、N+1、事务序列化失败、async vs sync 吞吐。各章(`../02`/`../05`/`../04`/`../06`)引用这里跑出的真数字。

## 跑起来

需要 Docker(Docker Desktop / OrbStack / colima 任一)。

```bash
cd python-data/lab
docker compose up -d            # 起 Postgres 16(localhost:5432/datalab)
uv sync                         # 装依赖(SQLAlchemy/psycopg/asyncpg/alembic)
uv run python seed.py           # 建表 + 灌 20 authors / 100 books / 1 account
```

数据库连接默认 `postgres:postgres@localhost:5432/datalab`,可用 `PG_HOST/PG_USER/PG_PASSWORD` 覆盖(见 `db.py`)。

## 四个 demo

```bash
uv run python demos/pool_exhaustion.py   # 池耗尽 → QueuePool TimeoutError
uv run python demos/n_plus_one.py        # lazy 21 条 vs selectinload 2 条
uv run python seed.py && \
uv run python demos/isolation.py         # SERIALIZABLE → SQLSTATE 40001
uv run python demos/async_vs_sync.py     # 20 并发:sync vs async 吞吐
```

> `isolation.py` 会改 `accounts.balance`,跑前先 `seed.py` 复位。

迁移演示(配 [ch07](../07-migrations.md)):

```bash
uv run python -c "from db import make_engine; from models import Base; Base.metadata.drop_all(make_engine())"  # 清空
uv run alembic revision --autogenerate -m "initial schema"   # 对比模型与库,生成迁移
uv run alembic upgrade head                                  # 应用;alembic current 看版本
uv run python seed.py                                        # 复原,继续其它 demo
```

> `seed.py` 用 `create_all` 走快捷路径;`alembic/` 是独立的真迁移演示,两者产出同一 schema。

## 实测数字(本机)

> Postgres 16 / SQLAlchemy 2.0.51 / psycopg 3.3.4 / asyncpg 0.31.0 / Python 3.11 / Apple Silicon。**你的数字会不同**;完整输出见 `CAPTURED.md`。

| demo | 现象 | 数字 |
|---|---|---|
| pool_exhaustion | 池满后第三个 checkout 等 `pool_timeout` 才报错 | 等 **1.00s** → `QueuePool limit of size 2 overflow 0 ... timed out` |
| n_plus_one | lazy 加载发 1+N 条;selectinload 收成 2 条 | **21 → 2** 条;35.5ms → 4.5ms |
| isolation | SERIALIZABLE 下读写冲突,第二个提交被中止 | **SQLSTATE 40001** `SerializationFailure` |
| async_vs_sync | 大量并发 IO,async 并发 vs sync 串行 | 1.07s → 0.28s,**~3.7x** |

## 文件

| 文件 | 作用 |
|---|---|
| `docker-compose.yml` | Postgres 16 |
| `db.py` | sync/async engine 工厂(psycopg / asyncpg) |
| `models.py` | `Author`/`Book`/`Account`(SQLAlchemy 2.0 风格) |
| `seed.py` | 建表 + 灌可复现数据 |
| `demos/` | 四个现象各一个独立脚本 |
| `alembic/` + `alembic.ini` | 迁移演示(env.py 接 `models.Base.metadata`),配 ch07 |
| `CAPTURED.md` | 实测原始输出存档 |

> 关停:`docker compose down`(加 `-v` 连数据卷一起删)。
