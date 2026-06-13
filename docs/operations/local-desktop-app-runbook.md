# 本地桌面应用端运行手册

日期：2026-06-13  
适用范围：`/Users/j/Documents/gupiao` 本地开发与验收  
状态：第一版，本地只读诊断 + Tauri 桌面壳

## 1. 边界

本地桌面端第一版只做：

- 加载现有 `frontend-next`。
- 默认进入 `/next/monitor`。
- 提供 `/next/local-status` 本机状态页。
- 保存/清除本机 API base URL。
- 查看后端、数据库、Redis、runtime worker、runtime scheduler 的只读状态。
- 打开本机日志目录和数据目录。

本地桌面端第一版不做：

- 不部署、不切流、不重启生产服务。
- 不清理 Docker、镜像、日志、缓存或磁盘。
- 不修改 `.env`、nginx、数据库结构或生产配置。
- 不自动下单。
- 不启动/停止 Docker、worker 或 scheduler。
- 不在桌面端重算策略、排序、回测、尾盘状态。

## 2. 本地依赖

需要本机具备：

- Node.js / npm
- Rust / Cargo
- Xcode Command Line Tools
- Tauri CLI，项目内通过 `frontend-next` devDependency 提供

检查命令：

```bash
npm --prefix frontend-next run desktop:info
```

## 3. 后端状态接口

接口：

```text
GET /api/local/status
```

返回内容：

- `backend`
- `mysql`
- `redis`
- `runtime_worker`
- `runtime_scheduler`
- 本机目录状态
- 当前 git version
- 固定安全边界

安全边界固定为：

```json
{
  "deploy_allowed": false,
  "restart_production_allowed": false,
  "cleanup_allowed": false,
  "auto_trade_allowed": false,
  "strategy_mutation_allowed": false
}
```

该接口只读；数据库、Redis 或 runtime 检查失败时，单项返回 `error` 或 `unknown`，接口整体仍应返回 HTTP 200。

## 4. 前端入口

普通 Web 构建：

```bash
npm --prefix frontend-next run build
```

本机状态页：

```text
/next/local-status
```

页面能力：

- API Base URL 输入框。
- 保存后重新检测。
- backend 不可达时不白屏。
- 日志目录入口。
- 数据目录入口。
- 本机启动引导；只展示命令，不自动执行。
- 安全边界展示。

本机启动引导命令来自项目既有本地入口：

```bash
scripts/run_platform_component.sh web
scripts/run_platform_component.sh runtime-worker
scripts/run_platform_component.sh scheduler
scripts/run_platform_component.sh analytics-worker
```

桌面端只展示这些命令，不调用 shell、不启动进程、不停止进程。

## 5. 桌面应用

开发模式：

```bash
npm --prefix frontend-next run desktop:dev
```

构建 macOS app：

```bash
npm --prefix frontend-next run desktop:build
```

当前第一版 bundle 目标为 `.app`：

```text
frontend-next/src-tauri/target/release/bundle/macos/TQuant Local.app
```

构建本地 DMG：

```bash
npm --prefix frontend-next run desktop:build:dmg
```

DMG 产物：

```text
frontend-next/src-tauri/target/release/bundle/dmg/TQuant Local_0.9.0_aarch64.dmg
```

说明：当前 `.app` 与 DMG 均可本地生成。DMG 已通过 `hdiutil verify` 和挂载内容检查；尚未配置 Developer ID 签名、公证和 stapling，因此仍是本地验收包，不是正式对外分发包。

## 6. 常见问题

### 6.1 backend 不可达

表现：

- `/next/local-status` 显示后端异常。

处理：

- 检查 API Base URL 是否正确。
- 按项目既有本地后端启动方式启动 backend。
- 重新点击“重检”。

### 6.2 Redis 未配置

表现：

- Redis 状态为 `未知`。

处理：

- 本地未启用 Redis 时可忽略。
- 需要缓存能力时，按项目本地环境文档启用 Redis。

### 6.3 Worker 或 Scheduler 未运行

表现：

- `runtime_worker` 或 `runtime_scheduler` 状态为 `未知`。

处理：

- 本轮桌面端只提示状态，不启动或停止 worker。
- 如需运行后台任务，按项目既有本地 worker 启动命令处理。

### 6.4 桌面构建失败

先执行：

```bash
npm --prefix frontend-next run desktop:info
```

再执行：

```bash
npm --prefix frontend-next run desktop:build
```

若失败集中在 DMG 打包，不影响 `.app` 第一版；可先使用 `.app` 完成本地验证。

### 6.5 分发签名/公证

当前本地包为开发验收产物。正式分发前需要补充：

- Apple Developer ID 签名。
- Hardened Runtime 与必要 entitlements 审核。
- notarization 与 stapling。
- `spctl --assess --type execute --verbose=2` 通过。

当前本机检查结果：

```bash
security find-identity -v -p codesigning
```

结果：`0 valid identities found`。因此正式签名/公证需要先提供 Apple Developer ID 证书和 notarytool 凭据。

## 7. 验收命令

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_local_desktop_status.py \
  backend/tests/test_local_desktop_status_api.py \
  backend/tests/test_priority_board_cache_fast_path.py \
  backend/tests/test_strategy_engine_production_gate_guards.py

npm --prefix frontend-next test -- --run \
  src/shared/api/runtimeBaseUrl.test.ts \
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
