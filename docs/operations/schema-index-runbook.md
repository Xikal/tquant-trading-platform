# Schema / Index Runbook

## 目标

生产环境的表结构和索引变更必须通过 Alembic 迁移完成。应用启动路径只允许做只读 schema drift 检查，不能隐式创建生产索引。

## 本地审计

```bash
PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py
```

严格模式：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py --strict
```

指定数据库：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py --database-url "$DATABASE_URL" --strict
```

## 迁移要求

- 新增索引必须写入 `backend/alembic/versions/`。
- 每个迁移必须提供 downgrade。
- MySQL 上线前执行：

```bash
cd backend
alembic upgrade head
PYTHONPATH=. python ../scripts/schema_index_audit.py --strict
```

## 运行时策略

- `SCHEMA_COMPAT_REPAIR_ENABLED=false` 是生产默认值。
- `schema_compat` 不再默认创建索引。
- 如自托管实例需要一次性修复旧表字段，只允许短时间显式开启 `SCHEMA_COMPAT_REPAIR_ENABLED=true`，完成后关闭。
