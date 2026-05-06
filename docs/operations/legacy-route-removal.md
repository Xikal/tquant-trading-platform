# Legacy Route Removal Runbook

## 范围

旧前端入口：

- `/backtests`
- `/research`

默认返回结构化 `410 LEGACY_ROUTE_REMOVED`，提示使用新的策略工作台入口。若需要短期兼容旧书签或外部脚本，可显式开启：

```env
LEGACY_ROUTE_COMPAT_ENABLED=true
```

开启后旧入口会临时 `301` 到：

- `/strategy?tab=backtest`
- `/strategy?tab=replay`

## 调用审计

```bash
python3 scripts/audit_legacy_routes.py
```

严格模式：

```bash
python3 scripts/audit_legacy_routes.py --strict
```

## 退役原则

- 第一方代码不得依赖 `/backtests` 或 `/research`。
- 新页面、Hermes workflow、飞书机器人和 QA 脚本必须使用 `/strategy` 或 `/api/backtests`。
- 兼容开关仅作为临时回滚手段，不作为长期入口。
