# Alembic 迁移说明

当前项目仍保留 `app.core.schema_compat` 的启动兼容逻辑，Alembic 用于后续生产化可审计迁移。

常用命令：

```bash
cd backend
.venv/bin/alembic -c alembic.ini revision --autogenerate -m "describe change"
.venv/bin/alembic -c alembic.ini upgrade head
```

迁移默认读取 `backend/.env` 与 `backend/data/runtime.env` 中的 `DATABASE_URL`。
