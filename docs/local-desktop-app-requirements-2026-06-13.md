# 本地桌面应用端需求文档

状态：收敛版，待评审  
日期：2026-06-13  
适用项目：`/Users/j/Documents/gupiao`  
目标：把当前本地 Web 平台包装成可日常使用的桌面应用端，不重写交易系统，不扩大成复杂客户端平台。

## 1. 结论

做桌面应用端是可行的，但必须控制边界。

一次到位的最优方案是：

```text
Tauri 桌面壳
  -> 加载现有 frontend-next
  -> 调用本机 backend API
  -> 提供本地服务健康检查
  -> 提供日志/数据目录入口
  -> 不承载策略计算、不承载数据库、不自动下单
```

不做 Electron 优先、不做原生重写、不做完全单体 exe、不做移动端、不做自动交易、不做线上部署控制台。

## 2. 要解决的问题

当前本地服务可以运行，但使用体验仍像开发环境：

- 需要记住前端地址。
- 不清楚 backend 是否启动。
- 不清楚 MySQL、Redis、worker 是否正常。
- 页面打不开时，不知道是 API、端口、服务还是前端资源问题。
- 日志和数据目录分散。

桌面应用端只解决这些本地使用问题，不改变交易平台的业务内核。

## 3. 范围

### 3.1 必须做

1. macOS 桌面应用入口。
2. 使用 Tauri 承载 `frontend-next`。
3. 默认打开 `/next/monitor`。
4. 支持配置本机 API 地址，默认 `http://127.0.0.1:<backend-port>`。
5. backend 不可达时显示诊断页，不白屏。
6. 展示本地核心服务状态：
   - backend API
   - MySQL
   - Redis
   - runtime worker
   - runtime scheduler
7. 提供日志目录入口。
8. 提供数据目录入口。
9. 提供端口冲突提示。
10. 保留现有 `frontend-next` 页面，不重做 UI。

### 3.2 明确不做

1. 不把 Python backend、MySQL、Redis、worker 全部嵌进单个 exe。
2. 不把 `frontend-next` 改成原生桌面 UI。
3. 不做 Electron 版本，除非 Tauri 被验证不可行。
4. 不做手机 App。
5. 不做自动更新系统。
6. 不做复杂插件市场或多工作区。
7. 不做线上部署、切流、重启入口。
8. 不做生产配置编辑器。
9. 不做自动真实交易下单。
10. 不在桌面端实现策略计算、排序、回测或尾盘状态判断。

## 4. 产品形态

桌面应用包含两个主区域：

| 区域 | 作用 |
| --- | --- |
| 主页面 | 直接显示现有 `frontend-next` 页面 |
| 本地状态抽屉/页面 | 显示本机服务状态、日志、数据目录和故障提示 |

默认进入主页面。只有在 backend 不可达、readyz 失败或用户主动打开时，才展示本地状态页。

## 5. 页面承载范围

桌面端第一版只承载现有 Web 页面：

| 页面 | 要求 |
| --- | --- |
| `/next/monitor` | 默认首页，保留 priority board 和尾盘推荐榜 |
| `/next/monitor/market` | 保留市场监控 |
| `/next/strategy-tracking` | 保留策略追踪 |
| `/next/analysis` | 保留分析页 |
| `/next/backtest` | 保留回测入口 |
| `/next/data` | 保留数据页 |
| `/next/settings` | 保留设置页 |

桌面端不得重算排序、状态、策略分、尾盘确认结果。所有业务结果以后端 API 为准。

## 6. 本地状态检查

### 6.1 状态项

| 服务 | 检查方式 | 展示 |
| --- | --- | --- |
| backend API | `/readyz` 或 `/api/readyz` | 可用/不可用、耗时 |
| MySQL | 后端健康接口返回 | 可用/不可用 |
| Redis | 后端健康接口返回 | 可用/不可用 |
| runtime worker | runtime workers/summary 接口 | 在线/离线、队列数 |
| runtime scheduler | heartbeat 或 runtime summary | 在线/离线 |
| frontend-next | 本地资源加载结果 | 正常/资源缺失 |

### 6.2 状态等级

只保留三档，避免过度复杂：

- `正常`
- `异常`
- `未知`

### 6.3 故障提示

必须能提示：

- backend 未启动。
- API 地址配置错误。
- 端口被占用。
- MySQL 不可用。
- Redis 不可用。
- worker 未运行。
- 前端资源加载失败。

提示只给出建议命令或文档入口，默认不自动执行修复。

## 7. 本地配置

桌面端只需要保存少量本地配置：

| 配置 | 默认值 |
| --- | --- |
| API base URL | `http://127.0.0.1:<backend-port>` |
| 是否显示状态页入口 | 是 |
| 日志目录 | 项目既有日志目录 |
| 数据目录 | 项目既有数据目录 |

配置保存到桌面应用自己的本地配置文件，不写生产 `.env`。

## 8. 启动与服务管理

### 8.1 第一版只做检查和引导

第一版不做一键启动全部服务。原因：

- 自动启动 Docker/worker 涉及本地权限和状态判断。
- 项目当前服务较多，过早做一键编排容易扩大范围。
- 先把“可见、可诊断、可引导”做好，更稳。

第一版可以显示：

- 当前服务是否可用。
- 如果不可用，建议用户运行哪个本地命令。
- 去哪里查看日志。

### 8.2 后续可选增强

只有在第一版稳定后，才考虑：

- 一键启动本地 compose。
- 一键查看指定容器日志。
- 一键停止非核心 worker。

这些都必须限定为本机操作，且执行前二次确认。

## 9. 安全边界

桌面端必须遵守：

1. 不自动下单。
2. 不连接生产服务器作为默认目标。
3. 不执行部署脚本。
4. 不执行切流。
5. 不重启生产服务。
6. 不清理磁盘、镜像、日志或缓存。
7. 不修改 `.env`。
8. 不修改 nginx。
9. 不修改数据库结构。
10. 不修改 `backend/app/services/low_buy/strategy_policy.py`。
11. 不改变 `production_score`、生产策略准入、priority board 默认排序和字段语义。
12. 不让 WebView 或桌面端触发全市场扫描、24M 回测、DuckDB 报告或重分析任务。

## 10. 当前未完成事项影响

| 未完成项 | 是否影响桌面端 |
| --- | --- |
| 尾盘 14:50/14:55/14:57 自动调度未上线 | 不影响。桌面端只展示后端已有状态 |
| 尾盘快照生产持久化未最终确认 | 不影响。桌面端只消费 API |
| 真实历史样本回放未完成 | 不影响桌面壳 |
| 旧前端未完全移除 | 低影响。桌面端只加载 `frontend-next` |
| 本地 worker/scheduler 一键管理未产品化 | 影响高级体验，不阻塞第一版 |

结论：这些未完成项不阻塞桌面端第一版。

## 11. 一次到位但不过度的版本定义

第一版完成后，用户应能：

1. 双击打开桌面应用。
2. 直接看到 `/next/monitor`。
3. backend 正常时完整使用现有 Web 功能。
4. backend 异常时看到诊断页。
5. 看到 backend、MySQL、Redis、worker、scheduler 的基本状态。
6. 打开日志目录。
7. 打开数据目录。
8. 修改本机 API 地址。
9. 确认桌面端没有执行部署、重启、清理或生产配置修改。

不要求第一版做到：

- 安装后自动拉起所有服务。
- 自动修复服务。
- 自动更新。
- 移动端同步。
- 多环境管理。
- 原生重写所有页面。

## 12. 技术选择

| 项 | 选择 |
| --- | --- |
| 桌面框架 | Tauri |
| 前端 | 复用 `frontend-next` |
| 后端 | 复用现有 FastAPI |
| 服务状态 | 通过现有 health/runtime API 获取 |
| 本地配置 | Tauri app config / 本地 JSON |
| 打包目标 | macOS 优先 |

Electron 只作为备选，不进入第一版。

## 13. 需要新增或确认的接口

优先复用现有接口。只有现有接口不足时，才新增一个轻量只读接口：

```text
GET /api/local/status
```

返回：

- backend 状态
- MySQL 状态
- Redis 状态
- runtime worker 状态
- runtime scheduler 状态
- 当前 git/version 信息

该接口只读，不触发刷新、扫描、回测或后台任务。

## 14. 验收标准

1. 桌面应用能在 macOS 启动。
2. 默认页面为 `/next/monitor`。
3. backend 正常时，priority board 和尾盘推荐榜可显示。
4. backend 不可达时不白屏，显示诊断页。
5. 状态页能显示 backend、MySQL、Redis、runtime worker、scheduler。
6. API 地址可配置并持久化。
7. 日志目录和数据目录可打开。
8. 禁止操作边界有明确文案。
9. 前端构建通过。
10. 后端核心回归通过。
11. `strategy_policy.py` 无 diff。
12. 未执行部署、切流、重启、清理、生产配置修改。

## 15. 测试要求

### 15.1 桌面端

- 启动测试。
- API base URL 保存/读取测试。
- backend 不可达降级页测试。
- 状态接口 mock 测试。
- 端口不可达提示测试。

### 15.2 前端

- `npm --prefix frontend-next run typecheck`
- `npm --prefix frontend-next run build`
- `/next/monitor` 基本渲染检查。

### 15.3 后端

- health/status 接口测试。
- runtime summary 读取测试。
- priority board cache 回归。
- late-session board cache 回归。

## 16. 最终判断

桌面端第一版不应该做成“完整本地运维平台”，也不应该重写业务功能。它应该是一个稳定、克制的本地应用入口：

- 业务继续由现有 Web 和后端承担。
- 桌面端只解决打开、连接、诊断和本地目录入口。
- 后续需求继续通过 backend API + `frontend-next` 增长，桌面端不需要大改。
