# M1 Lab

這個 Lab 以 PostgreSQL 18.4 執行 01–06 章的情境，並把觀察結果寫成可提交、可重現的
evidence。所有命令都從本目錄執行。

## 從啟動到清理

```bash
uv sync --locked
make db-up
make evidence
make verify
make db-down
```

| 命令 | 用途 |
|---|---|
| `make db-up` | 啟動 Compose 的 PostgreSQL 18.4，並等待 healthcheck 通過。 |
| `make evidence` | 依固定順序執行環境擷取與 01–06 章 scenarios，重建七份 evidence。 |
| `make verify` | 執行 Ruff、mypy、unit tests 與 PostgreSQL integration tests。 |
| `make db-down` | 停止 PostgreSQL 並刪除本機 Compose volume；應在 evidence 與測試結果審閱後執行。 |

> **破壞性操作警告**：`make evidence` 會在執行情境時刪除並重建 Lab schema。它只能指向
> 專用的本機測試資料庫，絕不可把 `SQLALCHEMY_DATABASE_URL` 設成 shared、staging 或
> production 資料庫。

本機資料庫 URL：

```text
postgresql+psycopg://sqlalchemy:sqlalchemy@localhost:55432/sqlalchemy_handson
```

`sqlalchemy`／`sqlalchemy` 是僅供本機使用的 Compose 預設帳密。提交的
[`environment.md`](evidence/environment.md) 只會保留遮蔽密碼後的 URL。

## Scenario 與 evidence 對照

| Scenario | Evidence | 精確目的 |
|---|---|---|
| [`environment.py`](scenarios/environment.py) | [`environment.md`](evidence/environment.md) | 記錄實際 Python、SQLAlchemy、psycopg、PostgreSQL 與主機平台版本，不洩漏密碼。 |
| [`ch01_engine_execution.py`](scenarios/ch01_engine_execution.py) | [`ch01-engine-execution.md`](evidence/ch01-engine-execution.md) | 觀察首次執行的 pool checkout、SQL 編譯與 bind parameter 路徑。 |
| [`ch02_schema_types.py`](scenarios/ch02_schema_types.py) | [`ch02-schema-types.md`](evidence/ch02-schema-types.md) | 重建並反射 M1 schema，驗證具名 constraints、JSONB 與 partial index。 |
| [`ch03_expression_compiler.py`](scenarios/ch03_expression_compiler.py) | [`ch03-expression-compiler.md`](evidence/ch03-expression-compiler.md) | 驗證 SQL 結構與 bound values 分離，且等價 statement 重用 compiled cache。 |
| [`ch04_core_dml_results.py`](scenarios/ch04_core_dml_results.py) | [`ch04-core-dml-results.md`](evidence/ch04-core-dml-results.md) | 重建資料後執行 tenant-scoped executemany、upsert、inventory DML 與報表。 |
| [`ch05_connection_transactions.py`](scenarios/ch05_connection_transactions.py) | [`ch05-connection-transactions.md`](evidence/ch05-connection-transactions.md) | 重建資料後重現 autobegin、例外 rollback、savepoint 與 PostgreSQL failed transaction。 |
| [`ch06_pooling_capacity.py`](scenarios/ch06_pooling_capacity.py) | [`ch06-pooling-capacity.md`](evidence/ch06-pooling-capacity.md) | 以固定 pool budget 飽和兩條連線，驗證第三次 checkout timeout 與回收。 |

## 疑難排解

| 症狀 | 檢查與處理 |
|---|---|
| Docker 無法使用 | 執行 `docker info`；若 daemon 未啟動，先啟動 Docker Desktop 或 OrbStack，再執行 `make db-up`。 |
| `55432` port 已被占用 | 執行 `lsof -nP -iTCP:55432 -sTCP:LISTEN` 找出占用者。停止衝突服務，或同步修改 `compose.yaml` port 與 `SQLALCHEMY_DATABASE_URL`。 |
| PostgreSQL 不健康 | 用 `docker compose ps` 查看狀態，再以 `docker compose logs postgres` 檢查 healthcheck／啟動錯誤；修正後重跑 `make db-up`。 |
| lockfile 過期 | `uv sync --locked` 會拒絕與 `pyproject.toml` 不一致的 lockfile。若依賴變更是刻意的，執行 `uv lock` 並審閱 `uv.lock`；否則還原非預期的依賴變更。 |
