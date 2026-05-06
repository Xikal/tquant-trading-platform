# Alembic 迁移说明

生产部署以 Alembic 为主迁移路径。`app.core.schema_compat` 默认只做只读漂移检查；
只有在自托管旧库需要一次性救援时，才显式设置 `SCHEMA_COMPAT_REPAIR_ENABLED=true`。

常用命令：

```bash
cd backend
.venv/bin/alembic -c alembic.ini revision --autogenerate -m "describe change"
.venv/bin/alembic -c alembic.ini upgrade head
```

Docker/MySQL 部署会先执行 `migration` 服务运行 `alembic upgrade head`，再启动 Web/worker。

迁移默认读取 `backend/.env` 与 `backend/data/runtime.env` 中的 `DATABASE_URL`。
