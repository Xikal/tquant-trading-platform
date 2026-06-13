# 本地桌面应用端实现提示词

你在 `/Users/j/Documents/gupiao` 工作。目标：按 `docs/local-desktop-app-requirements-2026-06-13.md` 和 `docs/local-desktop-app-development-doc-2026-06-13.md` 实现本地桌面应用端第一版，只做本地开发、测试、验收文档；不部署、不切流、不重启生产、不改生产配置。

开始前执行：
1. `cd /Users/j/Documents/gupiao && git status --short`
2. 阅读 `AGENTS.md`、`docs/engineering-conventions.md`、`docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`
3. 阅读上述需求文档和开发文档。

硬边界：
- 禁止部署/切流/重启生产/清理磁盘或 Docker/改 `.env`、nginx、数据库。
- 禁止改 `backend/app/services/low_buy/strategy_policy.py`。
- 禁止改变 `production_score`、生产准入、priority board 默认排序/字段语义。
- 禁止让 WebView/桌面端/新增 API 触发全市场扫描、24M 回测、DuckDB 报告或重分析。
- 禁止自动下单。
- 不做 Electron、手机 App、自动更新、完整单体 exe、复杂服务编排、线上运维控制台。
- 桌面端不得重算策略、排序、回测、尾盘状态；以后端 API 为准。

实现范围：
1. 后端只读接口 `GET /api/local/status`
   - 新增 `backend/app/models/schema_defs/local_desktop.py`
   - 新增 `backend/app/services/local_desktop_status.py`
   - 新增 `backend/app/api/routes/local_desktop.py`
   - 修改 `backend/app/api/router.py`
   - 新增 `backend/tests/test_local_desktop_status.py`
   - 新增 `backend/tests/test_local_desktop_status_api.py`
   - 返回 backend、MySQL/SQLite、Redis、runtime worker、runtime scheduler、目录、版本、安全边界；Redis 未配置为 `unknown`；DB 失败组件为 `error` 但整体 200；不泄露 password/token/secret/database_url；不入队任务。

2. frontend-next 运行时 API base URL
   - 新增 `frontend-next/src/shared/api/runtimeBaseUrl.ts`
   - 新增 `frontend-next/src/shared/api/runtimeBaseUrl.test.ts`
   - 修改 `frontend-next/src/shared/api/client.ts`
   - 支持保存/清除本机 API 地址；未配置时保持现有 `VITE_API_BASE_URL`/相对路径行为。

3. frontend-next 本机状态页 `/next/local-status`
   - 新增 `frontend-next/src/features/local-desktop/localDesktopModel.ts`
   - 新增 `frontend-next/src/features/local-desktop/localDesktopModel.test.ts`
   - 新增 `frontend-next/src/features/local-desktop/LocalDesktopStatusPage.tsx`
   - 新增 `frontend-next/src/features/local-desktop/local-desktop.css`
   - 修改 `frontend-next/src/app/routeTree.tsx`、`frontend-next/src/shared/config/routes.ts`
   - 显示 API 地址、保存/重检、backend/MySQL/Redis/worker/scheduler 状态、日志/数据目录入口、安全边界；backend 不可达不白屏；不得出现“必涨/建议买入/立即买入/自动下单/一键部署/重启生产”。

4. Tauri 桌面壳
   - 新增 `frontend-next/src-tauri/Cargo.toml`
   - 新增 `frontend-next/src-tauri/tauri.conf.json`
   - 新增 `frontend-next/src-tauri/src/main.rs`
   - 新增 `frontend-next/src-tauri/src/commands.rs`
   - 新增 `frontend-next/src-tauri/src/paths.rs`
   - 修改 `frontend-next/package.json`
   - 使用 Tauri v2，macOS 优先；脚本 `desktop:dev`、`desktop:build`、`desktop:info`；只允许 `read/write_desktop_config`、`open_log_dir`、`open_data_dir`，不得实现启动/停止 Docker、重启、清理、改 `.env`、部署。

5. 文档
   - 新增 `docs/operations/local-desktop-app-runbook.md`
   - 新增 `docs/reports/local-desktop-app-local-acceptance-2026-06-13.md`

多 Agent：
- A Backend：只改后端 local_desktop 相关和 `backend/app/api/router.py`。
- B Frontend：只改 runtimeBaseUrl、本机状态页、`client.ts`、`routeTree.tsx`、`routes.ts`。
- C Desktop：只改 `frontend-next/src-tauri/*`、`frontend-next/package.json`。
- D Integrator：只改 runbook/验收报告，跑全量测试。
- 共享文件锁：`router.py`=A，`client.ts/routeTree.tsx/routes.ts`=B，`package.json`=C。集成顺序 A→B→C→D。

验收命令：
```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_local_desktop_status.py backend/tests/test_local_desktop_status_api.py backend/tests/test_priority_board_cache_fast_path.py backend/tests/test_strategy_engine_production_gate_guards.py
npm --prefix frontend-next test -- --run src/shared/api/runtimeBaseUrl.test.ts src/features/local-desktop/localDesktopModel.test.ts
npm --prefix frontend-next run typecheck
npm --prefix frontend-next run build
npm --prefix frontend-next run desktop:info
npm --prefix frontend-next run desktop:build
git diff -- backend/app/services/low_buy/strategy_policy.py
git diff --check
git status --short
```

验收标准：macOS app 可构建；默认进 `/next/monitor`；`/next/local-status` 可用；backend 不可达不白屏；API base URL 可持久化；日志/数据目录可打开；`/api/local/status` 只读不泄密不触发重任务；无部署/重启/清理/生产配置入口；`strategy_policy.py` 无 diff；记录未部署、未重启、未切流、未改生产配置。
