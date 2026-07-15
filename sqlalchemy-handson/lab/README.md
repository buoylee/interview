# M1 Lab

## 啟動與驗證

```bash
cd lab
make sync
make db-up
make verify
```

本機資料庫 URL：

```text
postgresql+psycopg://sqlalchemy:sqlalchemy@localhost:55432/sqlalchemy_handson
```

> 警告：`sqlalchemy`／`sqlalchemy` 是僅供本機使用的 Compose 預設帳密，不得用於
> shared、staging 或 production 環境。
