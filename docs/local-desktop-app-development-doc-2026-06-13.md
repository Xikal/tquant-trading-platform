# 本地桌面应用端开发文档

状态：待实现  
日期：2026-06-13  
需求来源：`docs/local-desktop-app-requirements-2026-06-13.md`  
目标：一次到位实现克制版桌面应用端，不扩大成完整本地运维平台。

## 1. 总体结论

本轮只做：

```text
frontend-next + Tauri 桌面壳
  -> 默认打开 /next/monitor
  -> 支持运行时 API base URL
  -> 提供 /next/local-status 本机状态页
  -> 后端新增只读 /api/local/status
  -> 支持日志目录/数据目录入口
```

本轮不做：

- 不做 Electron。
- 不做手机 App。
- 不做自动更新。
- 不做单体 exe 内嵌 Python/MySQL/Redis/worker。
- 不做一键启动全部服务。
- 不做生产部署、切流、重启、清理入口。
- 不在桌面端重算策略、排序、回测、尾盘状态。

## 2. 架构

```text
macOS Tauri App
  frontend-next dist / dev server
    /next/monitor
    /next/local-status
    runtime API base URL
  Tauri Rust commands
    open_log_dir
    open_data_dir
    read_desktop_config
    write_desktop_config
  Backend FastAPI
    /readyz
    /api/local/status
    /api/runtime-tasks/summary
    /api/runtime-tasks/workers
```

桌面端只做容器和本地诊断，不承载业务计算。所有业务结果以后端 API 为准。

## 3. 文件规划

### 3.1 后端

| 文件 | 类型 | 职责 |
| --- | --- | --- |
| `backend/app/models/schema_defs/local_desktop.py` | 新增 | 定义本机状态 response schema |
| `backend/app/services/local_desktop_status.py` | 新增 | 聚合 DB、Redis、runtime worker、scheduler、目录、版本状态 |
| `backend/app/api/routes/local_desktop.py` | 新增 | 暴露 `GET /api/local/status` 只读接口 |
| `backend/app/api/router.py` | 修改 | include `local_desktop.router` |
| `backend/tests/test_local_desktop_status.py` | 新增 | 服务层测试 |
| `backend/tests/test_local_desktop_status_api.py` | 新增 | API 测试 |

### 3.2 frontend-next

| 文件 | 类型 | 职责 |
| --- | --- | --- |
| `frontend-next/src/shared/api/runtimeBaseUrl.ts` | 新增 | 运行时 API base URL 读取/保存/拼接 |
| `frontend-next/src/shared/api/runtimeBaseUrl.test.ts` | 新增 | API base URL 单测 |
| `frontend-next/src/shared/api/client.ts` | 修改 | `requestJson` 使用运行时 API base URL |
| `frontend-next/src/features/local-desktop/localDesktopModel.ts` | 新增 | 本机状态模型、状态文案、分组 |
| `frontend-next/src/features/local-desktop/localDesktopModel.test.ts` | 新增 | 本机状态模型单测 |
| `frontend-next/src/features/local-desktop/LocalDesktopStatusPage.tsx` | 新增 | 本机状态页 |
| `frontend-next/src/features/local-desktop/local-desktop.css` | 新增 | 状态页样式 |
| `frontend-next/src/app/routeTree.tsx` | 修改 | 增加 `/next/local-status` 路由 |
| `frontend-next/src/shared/config/routes.ts` | 修改 | 增加“本机状态”入口 |

### 3.3 Tauri

| 文件 | 类型 | 职责 |
| --- | --- | --- |
| `frontend-next/src-tauri/Cargo.toml` | 新增 | Tauri/Rust 依赖 |
| `frontend-next/src-tauri/tauri.conf.json` | 新增 | Tauri 构建、devUrl、frontendDist、权限 |
| `frontend-next/src-tauri/src/main.rs` | 新增 | app bootstrap |
| `frontend-next/src-tauri/src/commands.rs` | 新增 | 本地配置、打开目录命令 |
| `frontend-next/src-tauri/src/paths.rs` | 新增 | 项目目录、日志目录、数据目录解析 |
| `frontend-next/package.json` | 修改 | 增加 Tauri dev/build 脚本和 devDependency |

### 3.4 文档

| 文件 | 类型 | 职责 |
| --- | --- | --- |
| `docs/operations/local-desktop-app-runbook.md` | 新增 | 本地启动、验证、常见问题 |
| `docs/reports/local-desktop-app-local-acceptance-2026-06-13.md` | 新增 | 本地验收结果 |

## 4. 后端接口设计

### 4.1 Endpoint

```text
GET /api/local/status
```

要求：

- 只读。
- 不需要 admin 权限。
- 不返回密钥、密码、token、完整数据库 URL。
- 不触发刷新、扫描、回测、DuckDB 报告或后台任务。
- 单次请求应快速返回，单项检查失败不影响整体 response。

### 4.2 Response Schema

```python
class LocalDesktopComponentStatus(BaseModel):
    name: str
    status: Literal["ok", "error", "unknown"]
    latency_ms: int = 0
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class LocalDesktopDirectoryStatus(BaseModel):
    key: str
    path: str
    exists: bool


class LocalDesktopStatusResponse(BaseModel):
    generated_at: datetime
    app: str
    environment: str
    version: str = ""
    components: list[LocalDesktopComponentStatus]
    directories: list[LocalDesktopDirectoryStatus]
    safety: dict[str, bool]
```

### 4.3 Components

必须至少包含：

| name | 检查 |
| --- | --- |
| `backend` | 当前接口能返回即 ok |
| `mysql` | `ping_database()` |
| `redis` | `get_distributed_cache_client()` 后执行 `ping()`；无 Redis URL 时为 `unknown` |
| `runtime_worker` | `RuntimeTaskQueue(db).workers()` 有 active worker 或最近 heartbeat |
| `runtime_scheduler` | 查询 `platform_component_heartbeats` 中 `runtime-scheduler` 最近状态；查不到为 `unknown` |

说明：

- SQLite 本地模式下，`mysql` 组件可返回 `ok`，message 写明 `sqlite/local database ok`。
- Redis 未配置时返回 `unknown`，不是 `error`。
- worker/scheduler 查不到时不抛 500，返回 `unknown`。

### 4.4 Safety

固定返回：

```json
{
  "deploy_allowed": false,
  "restart_production_allowed": false,
  "cleanup_allowed": false,
  "auto_trade_allowed": false,
  "strategy_mutation_allowed": false
}
```

## 5. 前端设计

### 5.1 API Base URL

当前 `requestJson` 使用编译期 `VITE_API_BASE_URL`。桌面端需要运行时可配置，因此新增：

```ts
const STORAGE_KEY = "tquant.desktop.apiBaseUrl";

export function getRuntimeApiBaseUrl(): string {
  const value = localStorage.getItem(STORAGE_KEY) ?? "";
  return normalizeApiBaseUrl(value);
}

export function setRuntimeApiBaseUrl(value: string): void {
  const normalized = normalizeApiBaseUrl(value);
  if (normalized) localStorage.setItem(STORAGE_KEY, normalized);
  else localStorage.removeItem(STORAGE_KEY);
}

export function resolveApiUrl(path: string): string {
  const runtimeBase = getRuntimeApiBaseUrl();
  const buildBase = import.meta.env.VITE_API_BASE_URL ?? "";
  const base = runtimeBase || buildBase;
  return `${base}${path}`;
}
```

`requestJson` 改为：

```ts
const response = await fetchWithTimeout(resolveApiUrl(path), options, timeoutMs);
```

### 5.2 本机状态页

路由：

```text
/next/local-status
```

页面内容：

- API 地址输入框。
- 保存按钮。
- 重新检测按钮。
- 服务状态列表：backend、MySQL、Redis、runtime worker、runtime scheduler。
- 日志目录入口。
- 数据目录入口。
- 安全边界提示：未执行部署/重启/清理/生产配置修改。

backend 不可达时：

- 页面仍能渲染。
- 状态显示 `backend 异常`。
- 展示当前 API base URL。
- 提示用户先启动本地 backend。

### 5.3 文案要求

允许：

- `本机状态`
- `服务正常`
- `服务异常`
- `未知`
- `打开日志目录`
- `打开数据目录`
- `当前未执行部署、重启、清理或生产配置修改`

禁止：

- `必涨`
- `建议买入`
- `立即买入`
- `自动下单`
- `一键部署`
- `重启生产`

## 6. Tauri 设计

### 6.1 放置位置

Tauri 工程放在：

```text
frontend-next/src-tauri
```

原因：

- 复用现有 `frontend-next` Vite 构建。
- 不新增第二套前端。
- Tauri 官方 Vite 配置支持 `beforeDevCommand`、`beforeBuildCommand`、`devUrl`、`frontendDist`。

### 6.2 package scripts

修改 `frontend-next/package.json`：

```json
{
  "scripts": {
    "desktop:dev": "tauri dev",
    "desktop:build": "tauri build",
    "desktop:info": "tauri info"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2"
  },
  "dependencies": {
    "@tauri-apps/api": "^2"
  }
}
```

### 6.3 tauri.conf.json

```json
{
  "productName": "TQuant Local",
  "version": "0.1.0",
  "identifier": "cloud.weisilianghua.tquant.local",
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devUrl": "http://127.0.0.1:5173",
    "frontendDist": "../dist"
  },
  "app": {
    "windows": [
      {
        "title": "TQuant Local",
        "width": 1440,
        "height": 960,
        "minWidth": 1180,
        "minHeight": 760
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": ["app"],
    "category": "Productivity"
  }
}
```

### 6.4 Tauri commands

只允许本地低风险命令：

- `read_desktop_config`
- `write_desktop_config`
- `open_log_dir`
- `open_data_dir`

不实现：

- 启动 Docker。
- 停止 Docker。
- 重启服务。
- 清理目录。
- 修改 `.env`。
- 执行部署脚本。

## 7. 任务拆分

### Task 1：后端本机状态接口

**目标**：新增只读 `/api/local/status`。

**文件**：

- Create `backend/app/models/schema_defs/local_desktop.py`
- Create `backend/app/services/local_desktop_status.py`
- Create `backend/app/api/routes/local_desktop.py`
- Modify `backend/app/api/router.py`
- Create `backend/tests/test_local_desktop_status.py`
- Create `backend/tests/test_local_desktop_status_api.py`

**测试**：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_local_desktop_status.py \
  backend/tests/test_local_desktop_status_api.py
```

**验收**：

- `/api/local/status` 返回 200。
- Redis 未配置时是 `unknown`，不是 500。
- DB ping 异常时 mysql 组件为 `error`，整体仍返回 200。
- response 不含 password、token、secret、完整 database_url。
- 不触发 runtime task 入队。

### Task 2：运行时 API base URL

**目标**：前端支持运行时配置本机 API 地址。

**文件**：

- Create `frontend-next/src/shared/api/runtimeBaseUrl.ts`
- Create `frontend-next/src/shared/api/runtimeBaseUrl.test.ts`
- Modify `frontend-next/src/shared/api/client.ts`

**测试**：

```bash
npm --prefix frontend-next test -- --run src/shared/api/runtimeBaseUrl.test.ts
npm --prefix frontend-next run typecheck
```

**验收**：

- 未配置运行时 API base URL 时保持现有行为。
- 配置 `http://127.0.0.1:8000` 后，API 请求拼接到该地址。
- 空值会清除配置。
- 不影响现有 `VITE_API_BASE_URL` 用法。

### Task 3：本机状态页

**目标**：新增 `/next/local-status`。

**文件**：

- Create `frontend-next/src/features/local-desktop/localDesktopModel.ts`
- Create `frontend-next/src/features/local-desktop/localDesktopModel.test.ts`
- Create `frontend-next/src/features/local-desktop/LocalDesktopStatusPage.tsx`
- Create `frontend-next/src/features/local-desktop/local-desktop.css`
- Modify `frontend-next/src/app/routeTree.tsx`
- Modify `frontend-next/src/shared/config/routes.ts`
- Modify `frontend-next/src/shared/api/client.ts`

**测试**：

```bash
npm --prefix frontend-next test -- --run \
  src/features/local-desktop/localDesktopModel.test.ts
npm --prefix frontend-next run typecheck
npm --prefix frontend-next run build
```

**验收**：

- `/next/local-status` 可路由。
- backend 不可达时页面不白屏。
- 显示 backend、MySQL、Redis、runtime worker、runtime scheduler。
- 可保存 API base URL。
- 显示安全边界文案。

### Task 4：Tauri 桌面壳

**目标**：新增 macOS Tauri app 壳。

**文件**：

- Create `frontend-next/src-tauri/Cargo.toml`
- Create `frontend-next/src-tauri/tauri.conf.json`
- Create `frontend-next/src-tauri/src/main.rs`
- Create `frontend-next/src-tauri/src/commands.rs`
- Create `frontend-next/src-tauri/src/paths.rs`
- Modify `frontend-next/package.json`

**测试**：

```bash
npm --prefix frontend-next run desktop:info
npm --prefix frontend-next run desktop:build
cd frontend-next/src-tauri && cargo test
```

**验收**：

- macOS `.app` 能构建。
- 默认窗口加载 `frontend-next`。
- 不包含启动/停止/清理/部署命令。
- Rust commands 只能打开日志/数据目录和读写本地配置。

### Task 5：本地运行手册与验收报告

**目标**：补本文档化收尾。

**文件**：

- Create `docs/operations/local-desktop-app-runbook.md`
- Create `docs/reports/local-desktop-app-local-acceptance-2026-06-13.md`

**验收命令**：

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

git diff -- backend/app/services/low_buy/strategy_policy.py
git diff -- backend/app/services/low_buy/priority_board.py \
  backend/app/services/low_buy/priority_scoring.py \
  backend/app/services/low_buy/production_scoring.py \
  backend/app/services/low_buy/priority_response.py \
  backend/app/services/low_buy/strategy_policy.py
git status --short
```

## 8. 多 Agent 并行开发方案

允许多 Agent 并行开发，但必须按文件所有权隔离。每个 Agent 开始前都执行 `git status --short`，不得回滚、格式化或重排其他 Agent/用户已有改动；不得混入尾盘榜相关文件。

### 8.1 Agent 分工

| Agent | 负责范围 | 可改文件 | 禁止改文件 | 依赖 |
| --- | --- | --- | --- | --- |
| A Backend | `/api/local/status` 后端只读接口 | `backend/app/models/schema_defs/local_desktop.py`、`backend/app/services/local_desktop_status.py`、`backend/app/api/routes/local_desktop.py`、`backend/app/api/router.py`、`backend/tests/test_local_desktop_status*.py` | `backend/app/services/low_buy/*`、`frontend-next/*`、`frontend-next/src-tauri/*` | 无 |
| B Frontend | 运行时 API base URL 与 `/next/local-status` 页面 | `frontend-next/src/shared/api/runtimeBaseUrl.ts`、`runtimeBaseUrl.test.ts`、`frontend-next/src/features/local-desktop/*`、`frontend-next/src/app/routeTree.tsx`、`frontend-next/src/shared/config/routes.ts` | `frontend-next/src-tauri/*`、后端 low_buy 文件 | 需要 A 的 response schema 或按文档 schema mock |
| C Desktop | Tauri 壳与本地命令 | `frontend-next/src-tauri/*`、`frontend-next/package.json` | `backend/*`、`frontend-next/src/features/monitor-action/*` | 需要 B 保持 `npm run build` 可用 |
| D Integrator | runbook、验收报告、全量测试、冲突协调 | `docs/operations/local-desktop-app-runbook.md`、`docs/reports/local-desktop-app-local-acceptance-2026-06-13.md` | 不直接改业务实现，除非修复集成测试阻塞 | 等 A/B/C 完成 |

### 8.2 共享文件锁

以下文件容易冲突，只能由指定 Agent 改：

| 文件 | Owner |
| --- | --- |
| `backend/app/api/router.py` | Agent A |
| `frontend-next/src/shared/api/client.ts` | Agent B |
| `frontend-next/src/app/routeTree.tsx` | Agent B |
| `frontend-next/src/shared/config/routes.ts` | Agent B |
| `frontend-next/package.json` | Agent C |

如果其他 Agent 必须改共享文件，先在交付说明写明原因，并等待 Integrator 合并。

### 8.3 每个 Agent 的完成条件

Agent A：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_local_desktop_status.py \
  backend/tests/test_local_desktop_status_api.py
```

Agent B：

```bash
npm --prefix frontend-next test -- --run \
  src/shared/api/runtimeBaseUrl.test.ts \
  src/features/local-desktop/localDesktopModel.test.ts
npm --prefix frontend-next run typecheck
```

Agent C：

```bash
npm --prefix frontend-next run desktop:info
npm --prefix frontend-next run desktop:build
cd frontend-next/src-tauri && cargo test
```

Agent D：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_local_desktop_status.py \
  backend/tests/test_local_desktop_status_api.py \
  backend/tests/test_priority_board_cache_fast_path.py \
  backend/tests/test_strategy_engine_production_gate_guards.py
npm --prefix frontend-next run typecheck
npm --prefix frontend-next run build
git diff --check
git diff -- backend/app/services/low_buy/strategy_policy.py
```

### 8.4 集成顺序

1. 合并 Agent A，锁定 `/api/local/status` response schema。
2. 合并 Agent B，前端先用真实接口；backend 不可达路径仍要可用。
3. 合并 Agent C，确保 Tauri 使用同一份 `frontend-next` 构建。
4. Agent D 统一跑验收命令、补 runbook 和验收报告。

## 9. 验收标准

必须全部满足：

- macOS 桌面 app 可构建。
- `/next/monitor` 在桌面 app 中可显示。
- `/next/local-status` 可显示本机状态。
- backend 不可达时不白屏。
- API base URL 可配置并持久化。
- 日志目录和数据目录可打开。
- `/api/local/status` 为只读且不泄密。
- 不新增部署/重启/清理/生产配置修改入口。
- 不触发全市场扫描、24M 回测、DuckDB 报告或重分析。
- 不修改 `strategy_policy.py`。
- 不改变 `production_score`、priority board 默认排序和字段语义。

## 10. 参考

- Tauri v2 Create Project: `https://v2.tauri.app/start/create-project/`
- Tauri v2 Vite setup: `https://v2.tauri.app/start/frontend/vite/`
- Tauri v2 Desktop development: `https://v2.tauri.app/develop/`
- Tauri macOS bundle: `https://v2.tauri.app/distribute/macos-application-bundle/`
