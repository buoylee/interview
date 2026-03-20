# 01 — FastAPI 生产化部署

## 目标

理解"能跑"和"能上生产"的差距，建立一个作为后续所有实验载体的标准项目。

## 知识点清单

### 1. 进程模型
- [ ] Uvicorn 单进程 vs Gunicorn + UvicornWorker 多进程
- [ ] Worker 数量经验公式：`(2 × CPU核数) + 1`，适用场景限制
- [ ] 线程数（`--threads`）：何时有用，何时无效

### 2. 优雅关机
- [ ] SIGTERM 信号处理流程
- [ ] FastAPI `lifespan` 上下文管理器（替代 `on_startup/on_shutdown`）
- [ ] 连接排空：`--graceful-timeout` 配置

### 3. 健康检查
- [ ] `/health/live`：进程是否存活（Kubernetes liveness probe）
- [ ] `/health/ready`：依赖是否就绪（数据库、Redis 连通性）
- [ ] 健康检查不要做重型操作

### 4. 中间件
- [ ] 请求 ID 中间件（`X-Request-ID`，传播到日志和响应头）
- [ ] 耗时记录中间件（`X-Process-Time`）
- [ ] CORS / TrustedHost

### 5. 配置管理
- [ ] `pydantic-settings`：从环境变量/`.env` 文件读取配置
- [ ] 配置分层：base / development / production

### 6. 连接池
- [ ] SQLAlchemy async engine 配置（`pool_size` / `max_overflow`）
- [ ] aioredis / redis-py 连接池
- [ ] 依赖注入模式：`Depends(get_db)`

### 7. 容器化
- [ ] 多阶段 Dockerfile（builder + runtime）
- [ ] 非 root 用户运行
- [ ] Docker Compose：app + postgres + redis

## 实践代码

```
01-foundation/
├── app/
│   ├── main.py          # FastAPI app + lifespan
│   ├── config.py        # pydantic-settings
│   ├── middleware.py    # request_id, timing
│   ├── health.py        # /health/live, /health/ready
│   ├── database.py      # async SQLAlchemy
│   └── api/
│       └── orders.py    # 业务接口（后续阶段复用）
├── Dockerfile
├── docker-compose.yml
├── gunicorn.conf.py
└── requirements.txt
```

## 关键问题（能回答才算掌握）

1. Gunicorn + UvicornWorker 和纯 Uvicorn 多 worker 有什么区别？
2. `lifespan` 里如果数据库连接失败，服务会怎样？
3. 为什么健康检查接口不能查询业务数据库表？
4. `pool_size=5, max_overflow=10` 意味着最多几个连接？

## 参考

- [Uvicorn Deployment](https://www.uvicorn.org/deployment/)
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
