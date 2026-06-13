# 本地桌面应用端本地验收报告

日期：2026-06-13  
检查时间：2026-06-13 11:19:55 CST  
项目：`/Users/j/Documents/gupiao`  
范围：本地开发、测试、验收文档  
结论：第一版本地桌面应用端已实现并通过主要本地验收；未部署、未重启、未切流、未改生产配置。

## 1. Git 状态

开始前已执行：

```bash
cd /Users/j/Documents/gupiao && git status --short
```

开始前工作区已有尾盘推荐榜相关未提交改动；本轮未回退、未覆盖这些改动。

本轮新增/修改范围：

- 后端本机状态接口：`/api/local/status`
- frontend-next 运行时 API base URL
- `/next/local-status` 本机状态页
- Tauri v2 macOS 桌面壳
- 本运行手册与验收报告

受保护文件：

- `backend/app/services/low_buy/strategy_policy.py` 未修改

## 2. 实现总览

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 后端 `/api/local/status` | 已完成 | 只读聚合 backend、数据库、Redis、runtime worker、runtime scheduler、目录和安全边界 |
| 前端运行时 API base URL | 已完成 | 支持保存、清除、运行时覆盖；未配置时保持原相对路径或 `VITE_API_BASE_URL` 行为 |
| `/next/local-status` | 已完成 | 未登录时可从登录页进入；backend 不可达时仍渲染诊断状态，不白屏 |
| Tauri v2 桌面壳 | 已完成 | `desktop:info`、`desktop:build` 与 `desktop:build:dmg` 可通过，生成 macOS `.app` 与本地 DMG |
| 本地目录入口 | 已完成 | 仅支持打开日志目录、数据目录 |
| 本机启动引导 | 已完成 | 展示 Web/API、runtime-worker、scheduler、analytics-worker 本地命令；桌面端不执行命令 |
| 安全边界 | 已完成 | 不提供部署、重启、清理、生产配置、交易执行入口 |

## 3. 后端验收

新增文件：

- `backend/app/models/schema_defs/local_desktop.py`
- `backend/app/services/local_desktop_status.py`
- `backend/app/api/routes/local_desktop.py`
- `backend/tests/test_local_desktop_status.py`
- `backend/tests/test_local_desktop_status_api.py`

修改文件：

- `backend/app/api/router.py`

覆盖点：

- Redis 未配置返回 `unknown`。
- DB 异常时组件为 `error`，接口不泄露 password/token/secret/database_url。
- API 返回 HTTP 200，不入队 runtime task。
- API 返回本机启动引导命令，命令来自 `scripts/run_platform_component.sh`。
- 固定安全边界全部为 `false`。

## 4. 前端验收

新增文件：

- `frontend-next/src/shared/api/runtimeBaseUrl.ts`
- `frontend-next/src/shared/api/runtimeBaseUrl.test.ts`
- `frontend-next/src/features/local-desktop/localDesktopModel.ts`
- `frontend-next/src/features/local-desktop/localDesktopModel.test.ts`
- `frontend-next/src/features/local-desktop/tauriBridge.ts`
- `frontend-next/src/features/local-desktop/tauriBridge.test.ts`
- `frontend-next/src/features/local-desktop/LocalDesktopStatusPage.tsx`
- `frontend-next/src/features/local-desktop/local-desktop.css`

修改文件：

- `frontend-next/src/shared/api/client.ts`
- `frontend-next/src/shared/api/queryKeys.ts`
- `frontend-next/src/shared/config/routes.ts`
- `frontend-next/src/app/routeTree.tsx`
- `frontend-next/src/legacy-shell/legacyNavConfig.ts`
- `frontend-next/vite.config.ts`

覆盖点：

- 运行时 API base URL 只接受 `http` / `https`。
- 运行时 base URL 优先于构建时 base URL。
- 未配置时保持相对 API 路径。
- 桌面构建默认 API base URL 为 `http://127.0.0.1:8000`。
- Tauri 桌面壳内配置来源显示为 `Tauri 本地 JSON`。
- Tauri bridge 覆盖本地 JSON 读取、写入和目录打开命令。
- 本机状态模型能汇总异常/未知/正常。
- backend 不可达时返回可读兜底模型。
- backend 端口未监听或连接失败时显示端口提示。
- backend 不可达时仍展示本机启动引导命令。
- 模型测试覆盖禁止文案：`必涨`、`建议买入`、`立即买入`、`自动下单`、`一键部署`、`重启生产`。

## 5. Tauri 验收

新增文件：

- `frontend-next/src-tauri/Cargo.toml`
- `frontend-next/src-tauri/Cargo.lock`
- `frontend-next/src-tauri/build.rs`
- `frontend-next/src-tauri/tauri.conf.json`
- `frontend-next/src-tauri/capabilities/default.json`
- `frontend-next/src-tauri/src/main.rs`
- `frontend-next/src-tauri/src/commands.rs`
- `frontend-next/src-tauri/src/paths.rs`
- `frontend-next/src-tauri/icons/icon.png`
- `frontend-next/src-tauri/.gitignore`

修改文件：

- `frontend-next/package.json`
- `frontend-next/package-lock.json`

桌面命令：

| 命令 | 状态 | 说明 |
| --- | --- | --- |
| `read_desktop_config` | 已实现 | 读取本地 JSON 配置 |
| `write_desktop_config` | 已实现 | 仅保存 API base URL |
| `open_log_dir` | 已实现 | 仅打开本机日志目录 |
| `open_data_dir` | 已实现 | 仅打开本机数据目录 |

未实现且本轮明确禁止：

- 启动/停止 Docker
- 重启生产服务
- 清理磁盘/镜像/日志/缓存
- 修改 `.env`、nginx、数据库
- 部署或切流
- 自动下单

## 6. 构建产物

成功构建：

```text
frontend-next/src-tauri/target/release/bundle/macos/TQuant Local.app
frontend-next/src-tauri/target/release/bundle/dmg/TQuant Local_0.9.0_aarch64.dmg
```

DMG 状态：

- `hdiutil verify` 校验通过。
- 挂载后包含 `TQuant Local.app`。
- DMG 内应用 `CFBundleIdentifier=cloud.weisilianghua.tquant.local`，版本 `0.9.0`。
- 当前为本地验收包，尚未做 Developer ID 签名、公证和 stapling。

## 6.1 本地启动冒烟

执行时间：2026-06-13 11:30:50 CST

已执行：

```bash
/usr/bin/open -n "frontend-next/src-tauri/target/release/bundle/macos/TQuant Local.app"
```

结果：

- `TQuant Local` 进程成功启动，PID 为 `21698`。
- `lsappinfo` 识别到 `CFBundleIdentifier=cloud.weisilianghua.tquant.local`。
- 进程运行超过 1 分钟，未启动即崩溃。
- WebKit 日志显示主文档加载完成：`didFinishDocumentLoadForFrame`。
- WebKit 日志显示首次非空布局完成：`DidFirstVisuallyNonEmptyLayout`。
- WebKit 日志显示窗口可见：`window visible 1, view hidden 0, window occluded 0`。

限制：

- 本轮未用人工视觉点击逐页检查业务页面。
- 本轮未启动或修改本地 backend/Redis/worker；业务 API 可用性仍以 `/next/local-status` 和后端实际运行状态为准。

## 6.2 交互冒烟

执行时间：2026-06-13 11:46:57 CST

已验证：

- 未登录状态下，登录页存在“打开本机状态”入口。
- 点击“打开本机状态”后进入 `/next/local-status`。
- 页面显示 `本地量化桌面端`、`API 地址`、`日志目录`、`数据目录`、`安全边界`。
- 桌面构建默认 API 地址显示为 `http://127.0.0.1:8000`。
- 配置来源显示为 `Tauri 本地 JSON`，说明 Tauri bridge 可用。
- 本地 backend 未运行时，页面显示端口提示：`端口可能未监听或被占用，请检查本机 API 地址和后端端口`。
- 日志目录按钮已触发 Tauri 命令；当前本机 `logs` 目录不存在时，页面显示目录打开失败，不会执行创建或清理。
- 最终前端已修正为透传 Tauri 字符串错误；目录不存在时可显示后端命令返回的具体原因。
- 最终 Tauri 命令已修正为日志目录缺失时回退打开项目目录，不创建 `logs` 目录。

## 6.3 启动引导与签名检查

执行时间：2026-06-13 12:18 CST

已验证：

- `/next/local-status` 显示“本机启动引导”。
- 启动引导包含 `scripts/run_platform_component.sh web`、`runtime-worker`、`scheduler`、`analytics-worker`。
- 页面仅展示命令文本，没有启动/停止/重启按钮。
- `security find-identity -v -p codesigning` 返回 `0 valid identities found`。
- `xcrun notarytool --help` 可用，但当前缺少 Developer ID 证书和 notarytool 凭据，不能完成正式签名/公证。

说明：

- 首次尝试 `targets: all` 时，`.app` 已成功生成但 DMG 阶段 `bundle_dmg.sh` 失败；后续使用 `tauri build --bundles dmg --ci` 复跑成功。
- 默认 `desktop:build` 仍只生成 `.app`，避免每次本地构建都等待 DMG 打包。
- `desktop:build:dmg` 用于需要 DMG 验收时单独执行。

## 7. 已执行验证

已通过：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_local_desktop_status.py \
  backend/tests/test_local_desktop_status_api.py \
  backend/tests/test_priority_board_cache_fast_path.py \
  backend/tests/test_strategy_engine_production_gate_guards.py
```

结果：`16 passed, 1 warning`

已通过：

```bash
npm --prefix frontend-next test -- --run \
  src/shared/api/runtimeBaseUrl.test.ts \
  src/features/local-desktop/tauriBridge.test.ts \
  src/features/local-desktop/localDesktopModel.test.ts
```

结果：`14 passed`

已通过：

```bash
npm --prefix frontend-next run typecheck
npm --prefix frontend-next run build
npm --prefix frontend-next run desktop:info
npm --prefix frontend-next run desktop:build
npm --prefix frontend-next run desktop:build:dmg
hdiutil verify "frontend-next/src-tauri/target/release/bundle/dmg/TQuant Local_0.9.0_aarch64.dmg"
```

结果：均通过；`desktop:build` 生成 `.app`，`desktop:build:dmg` 生成 DMG，`hdiutil verify` 校验通过。

已通过：

```bash
cargo test --manifest-path frontend-next/src-tauri/Cargo.toml
```

结果：`5 passed`

已通过：

```bash
git diff -- backend/app/services/low_buy/strategy_policy.py
git diff --check
git status --short
```

结果：

- `strategy_policy.py` 无 diff。
- `git diff --check` 无输出。
- `frontend-next/src-tauri/target/` 已由 `frontend-next/src-tauri/.gitignore` 忽略，不纳入提交。
- `git status --short` 显示当前工作区仍包含本轮新增桌面端文件，以及本轮开始前已有的尾盘推荐榜相关未提交文件。

## 8. 完整验收命令

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_local_desktop_status.py \
  backend/tests/test_local_desktop_status_api.py \
  backend/tests/test_priority_board_cache_fast_path.py \
  backend/tests/test_strategy_engine_production_gate_guards.py

npm --prefix frontend-next test -- --run \
  src/shared/api/runtimeBaseUrl.test.ts \
  src/features/local-desktop/tauriBridge.test.ts \
  src/features/local-desktop/localDesktopModel.test.ts

npm --prefix frontend-next run typecheck
npm --prefix frontend-next run build
npm --prefix frontend-next run desktop:info
npm --prefix frontend-next run desktop:build
npm --prefix frontend-next run desktop:build:dmg
hdiutil verify "frontend-next/src-tauri/target/release/bundle/dmg/TQuant Local_0.9.0_aarch64.dmg"
cargo test --manifest-path frontend-next/src-tauri/Cargo.toml
git diff -- backend/app/services/low_buy/strategy_policy.py
git diff --check
git status --short
```

## 9. 本轮未执行事项

本轮未执行：

- 未部署。
- 未切流。
- 未重启生产服务。
- 未重启 Docker 或 systemd 服务。
- 未清理磁盘、Docker、镜像、日志、缓存。
- 未修改 `.env`。
- 未修改 nginx。
- 未修改数据库结构或生产数据。
- 未修改 `backend/app/services/low_buy/strategy_policy.py`。
- 未改变 `production_score`、生产策略准入、priority board 默认排序或默认字段语义。
- 未让 WebView、桌面端或新增 API 触发全市场扫描、24M 回测、DuckDB 报告或重分析任务。
- 未实现自动下单。

## 10. 后续建议

| 优先级 | 事项 | 说明 |
| --- | --- | --- |
| P1 | 签名与公证 | 本机 `0 valid identities found`；需 Developer ID 证书、notarytool 凭据、notarization、stapling 与 `spctl` 验收 |
| P2 | Finder 双击验收 | 当前已用 `/usr/bin/open` 与截图验证；正式交付前可补 Finder 双击人工记录 |
| P3 | 图标精修 | 当前图标为本地生成的最小 PNG，可后续替换为正式视觉资产 |
