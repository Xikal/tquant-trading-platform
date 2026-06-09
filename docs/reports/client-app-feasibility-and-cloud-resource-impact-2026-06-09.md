# 客户端化可行性 与 云服务器资源影响 分析报告（2026-06-09）

> 性质：**只做分析与方案，未改代码、未部署、未切流、未删除旧前端**。仅新增本报告。
> 基线：`git status --short` 显示有他人正在执行"平台瘦身"（大量 `D` 截图/回测 JSON + 新增 manifest/plan），本轮**未回滚这些在途改动**。
> 已读：`AGENTS.md`、`engineering-conventions.md`、模块化架构计划、`platform-slimming-audit-2026-06-09.md`、`platform-slimming-optimization-execution-plan-2026-06-09.md`、`frontend-next/{package.json,shared/api/client.ts,shared/workers/*}`、后端 routes/services（bff/low_buy/backtest/paper/tasks）、`docker-compose.mysql.yml`。
> 硬边界遵守：不改 `strategy_policy.py`/`production_score`/priority_board/生产排序；strategy_engine 仍 shadow-only；不把生产策略判断、正式模拟盘账本、MySQL 主写、数据刷新发布逻辑下沉客户端。

---

## 0. 一句话结论（先给最关键判断）

**客户端化（首选 PWA）对"用户体验/离线/分发"有明确价值，但对"显著降低云服务器资源占用"作用有限——因为本平台云端成本的主体是"全平台共享、与客户端数量无关的常驻基础设施"（MySQL + Redis + 数据刷新 Worker + Go 服务），这些按硬边界必须留在云端、且无论有几个客户端、是否本地缓存都照常运行。** 真正降云成本的杠杆是"Worker 按需化/瘦身/数据治理"，不是客户端化。客户端化值得做，但请以 UX 与分发为目标，不要以"省云钱"为主要理由。

---

## 1. 当前云服务器资源占用来源分类

`docker-compose.mysql.yml` 共 **13 个服务 + 4 个卷**，云端常驻面如下：

| 类别 | 服务/来源 | 资源特征 | 与客户端数量相关? | 客户端化能否卸载 |
|---|---|---|---|---|
| **数据事实源** | `mysql`（生产写/读、日线、账本）+ `mysql-backup` | 常驻、磁盘大、写路径 | **无关**（全平台一份） | ❌ 必须留云（硬边界4） |
| **缓存** | `redis`（行情/quote cache） | 常驻、内存 | 弱相关（读命中） | ⚠️ 部分（客户端缓存可减少重复读） |
| **API/BFF** | `app`（FastAPI sync）+ `go-bff-gateway` | 常驻、按请求 CPU | **相关**（请求量） | ⚠️ 部分（缓存命中降请求） |
| **行情读加速** | `go-market-read-service`、`go-scan-worker` | 常驻 | 弱相关 | ❌ 读路径留云 |
| **数据刷新 Worker** | `runtime-worker`、`runtime-scheduler` | 常驻、定时（quote cache/物化/daily bar/watchdog） | **无关**（发布一次给所有人） | ❌ 必须留云（硬边界4） |
| **回测 Worker** | `backtest-worker` | 常驻、按任务 | 无关（权威回测） | ❌ 权威回测留云（客户端只能 preview） |
| **分析层** | `analytics-worker`（DuckDB/Parquet 导出，已门控） | 按需、CPU/磁盘 | 无关 | ❌ 不得作生产事实源 |
| **数据文件** | `backend/data` 2.4G（parquet/duckdb/sqlite，gitignore，不进镜像但占盘） | 磁盘 | 无关 | ❌ 留云 |
| **回测/报告** | 24M 回测/导出产物 | 按需磁盘/CPU | 无关 | ⚠️ 浏览可客户端，生成留云 |
| **静态前端** | `app` 提供 `frontend/dist`（~2.7M） | 极低（几用户、静态文件） | 相关但**微不足道** | ✅ 可完全卸载（但省得少） |
| **日志/缓存** | 容器日志、本地缓存 | 低-中 | 弱相关 | ⚠️ 部分 |

**关键观察**：13 个服务里，**与客户端数量无关的常驻成本**（mysql/redis/2 worker/scheduler/3 Go/backup）= 绝大部分；与请求量相关的只有 `app`+`go-bff` 的 CPU，而本平台用户少、p95 已不高（market_pulse ~197ms、priority_board ~160ms），请求侧不是瓶颈。**静态前端托管成本可忽略**（几用户、1.2MB SPA）。

---

## 2. 适合下沉客户端 vs 必须留云端

### ✅ 适合下沉客户端（非生产事实源、展示/计算层）
- **展示渲染**：所有页面 UI（已是 SolidJS SPA）。
- **图表计算**：K 线（lightweight-charts）、降采样/缩放——`shared/workers/computeSync.ts` 已客户端 worker 化（filter/sort/downsample/derive）。
- **筛选/排序（展示层）**：lane 过滤、表格排序——**已在客户端**，且经审计确认不重排生产榜（只过滤）。
- **本地缓存**：API 响应的 IndexedDB 持久缓存 + SWR（客户端 `client.ts` 现有 offline 检测、timeout、retry，但**无持久缓存**，可补）。
- **报告浏览**：历史回测/24M 报告的**只读浏览**（数据由云端生成、客户端缓存渲染）。
- **研究/回测预览**：用已拉取的 run detail/trades 在客户端做**预览级**重排/对比/可视化（非权威结果）。

### ❌ 必须留云端（硬边界）
- **生产策略判断**：`strategy_policy`/`production_score`/priority_board 排序、低吸生产语义。
- **正式模拟盘账本**：paper 真实成交/持仓/账本写入（MySQL）。
- **MySQL 主写 + 数据刷新发布**：daily bar/quote cache/物化/收盘发布——一份给所有人，客户端不可承载。
- **权威回测/分析层**：backtest-worker、analytics DuckDB/Parquet——客户端只能 preview，不得作事实源。
- **行情读路径**：go-market-read/scan、provider 拉取、Redis 主缓存。
- **鉴权与 admin 写**：token 签发、admin 写操作必须经云端校验。

---

## 3. PWA / Tauri / Electron 三方案对比

| 维度 | PWA | Tauri | Electron |
|---|---|---|---|
| **开发成本** | **最低**：现有 Vite+Solid SPA 加 `vite-plugin-pwa`+manifest+SW，复用 100% frontend-next | 中：需 Rust 壳（仓库已有 Rust 工具链 `rust/tquant-rs`，但那是 PyO3 扩展，非 Tauri，需新建壳）+ 签名/更新 | 中-高：Node 主进程 + 打包链 |
| **性能** | 系统浏览器引擎，启动快 | 系统 WebView，原生级，内存低 | 自带 Chromium，内存高 |
| **客户端体积** | **~0 额外**（就是 SPA，~1.2MB JS） | **小**（~3–10MB，复用系统 WebView） | **大**（~80–150MB，捆绑 Chromium） |
| **离线能力** | SW 预缓存 + IndexedDB，**够用**（只读浏览/缓存） | 强（本地 FS/SQLite/sidecar） | 强 |
| **安全性** | Web 同源/CSP/HttpOnly，模型成熟 | 强（Rust + capability allowlist），但需管签名/自动更新安全 | 较弱（Node 全权限面大） |
| **维护成本** | **最低**（一套 web 资产，CI 不变） | 中（多平台构建/签名/更新通道） | 高（Chromium 升级/安全补丁/包体） |
| **分发** | 浏览器"添加到主屏"/桌面安装，无应用商店门槛 | 需打包安装包 | 需打包安装包 |
| **对降云成本** | 缓存命中降少量读请求 | 同 PWA（壳不影响云） | 同 PWA |

**结论**：**PWA 性价比最高**，复用现有 SPA、零额外运行时、安全模型成熟、维护最低。**Tauri** 仅在未来需要"桌面级离线 + 本地数据库 + 本地重计算 sidecar"时再上（可复用 Rust 工具链）。**Electron 不推荐**（体积大、内存高、维护重，对本平台无额外收益）。

---

## 4. 推荐架构（客户端 + 云端最小事实源 + Worker 边界图）

```
┌───────────────────────── 客户端（PWA，首选）─────────────────────────┐
│ SolidJS SPA  +  Service Worker（静态预缓存）                        │
│ ├─ 展示渲染 / lightweight-charts K线 / 图表降采样                    │
│ ├─ Web Worker computeSync：展示层 filter/sort/downsample（已存在）    │
│ ├─ IndexedDB：API 响应持久缓存 + SWR（行情/榜单/报告，短TTL）        │
│ └─ 只读浏览：历史回测/24M 报告、研究/回测 PREVIEW（用已拉数据）       │
│        ▲ 仅 GET / 缓存 / 展示；写操作直达云端鉴权                     │
└────────┼─────────────────────────────────────────────────────────┘
         │ HTTPS（OpenAPI 契约，token）
┌────────▼──────────────── 云端最小事实源（必须留）──────────────────┐
│ app(FastAPI/BFF) + go-bff-gateway   ← 鉴权 / 聚合 / 生产排序读        │
│ MySQL（生产写/账本/日线） + Redis（行情缓存）                         │
│ go-market-read / go-scan（行情读加速）                               │
│ ─ 写：paper 账本、settings、feature flag、admin → 必须云端校验 ─      │
└──────────────────────────────┬────────────────────────────────────┘
                                │ RuntimeTaskQueue（DB 队列）
┌───────────────────────────────▼───────────────── Worker（必须留）──┐
│ runtime-worker/scheduler：quote cache / 物化 / daily bar / 收盘发布   │
│ backtest-worker：权威回测      analytics-worker：DuckDB/Parquet（按需）│
└────────────────────────────────────────────────────────────────────┘
```
**边界铁律**：客户端只承载"非生产事实源"的展示/缓存/预览；生产排序、账本写、数据发布、权威回测/分析永远在云端。

---

## 5. 预估降本效果（诚实量化）

> 前提：本平台用户少、云成本主体是常驻基础设施。降本以"是否减少常驻/按请求资源"衡量。

| 措施 | 云端 CPU | 内存 | 磁盘 | 网络 | 评估 |
|---|---|---|---|---|---|
| **只打包客户端（PWA 静态化）** | ≈0 | ≈0 | ≈0 | 轻微↓（静态资源走 CDN/SW 缓存，首屏后不再回源） | **省得极少**：几用户的 1.2MB SPA 托管本就微不足道 |
| **本地缓存（IndexedDB+SWR，行情/榜单短TTL）** | 轻↓（重复 GET 减少 → app/go-bff/Redis 读↓） | ≈0 | ≈0 | **中↓**（重复读请求显著减少） | **请求侧小幅降**，但 Worker 仍按时刷新数据，MySQL/Redis 常驻不变 |
| **图表/报告本地化（已客户端 + 报告只读缓存）** | 轻↓（少量聚合/序列化压力） | ≈0 | ≈0 | 轻↓ | **小幅**：图表本就客户端；报告浏览本地化省少量序列化 |
| **研究/回测本地预览** | ≈0（权威回测仍在云 worker） | ≈0 | ≈0 | ≈0 | **几乎不降云**：preview 用已拉数据，权威 backtest-worker 照常 |
| —（对照）真正降云的非客户端杠杆 | **中-大↓** | 中↓ | 中-大↓ | — | analytics-worker 按需不常驻、scheduler 频率优化、backend/data 治理、瘦身（进行中） |

**总体**：客户端化（PWA+本地缓存）能让**与请求量相关的那部分（app/go-bff CPU + Redis/MySQL 读 + 出网带宽）小幅下降**；但**常驻大头（MySQL/Redis/Worker/Go 服务）= 0 下降**。在"少用户 + 常驻为主"的成本结构下，**客户端化无法显著降低云服务器总资源占用**。若云账单痛点真实存在，**优先做**：① `analytics-worker` 改按需启动（非常驻）；② scheduler 刷新频率与 worker 副本数右调；③ 进行中的瘦身（大产物出库）；④ MySQL/Redis 资源 right-size。

---

## 6. 安全风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| **token 暴露** | 客户端持有 access/refresh token（现 `client.ts` 内存 access + refresh 刷新） | 维持 HttpOnly refresh（Web）/ Tauri 用 OS keychain；access 短期内存态；不落明文 localStorage |
| **admin 写操作** | 客户端不得绕过云端鉴权做生产写 | 所有写直达云端校验；客户端只做 GET + 预览；沿用 mutation guard / safeWriteContracts |
| **本地缓存数据泄露** | IndexedDB 明文可被本机读取 | 只缓存**非敏感展示数据**（行情/公开榜单）；账户/持仓敏感数据短 TTL + 登出即清；Tauri 可加密本地库 |
| **离线伪造/陈旧误导** | 缓存数据被当成最新 | 强制 `stale/as_of/data_quality` 标识端到端透传（审计已确认）；离线显式"离线·缓存于 X"，不展示成新鲜 |
| **生产语义被客户端篡改** | 客户端重算分数/排序 | 硬边界：客户端只过滤展示、不重算 `production_score`/不重排 priority board（审计已确认 worker 仅 filter/sort/downsample） |
| **回滚** | 客户端版本与契约漂移 | PWA：SW 版本化 + 即时回滚到旧资产；OpenAPI 契约不兼容时客户端降级到"需更新"；旧前端 `frontend/` 保留可回退 |

---

## 7. API 与缓存策略

| 接口类 | 可缓存? | TTL | 离线/stale 原则 |
|---|---|---|---|
| 行情/quote（`/api/quote`,`screeners/.../quotes`） | 是 | 5–15s | 离线显示"缓存于 X · 离线"，不当实时 |
| 优先榜/monitor BFF（`/api/bff/v1/workspace/monitor`） | 是（SWR） | 30s（与后端刷新对齐） | `stale/snapshot_warning` 透传；离线只读 |
| 策略 BFF/strategy-tracking | 是 | 30–60s | 同上 |
| 回测 run detail/trades、24M 报告 | 是（强缓存） | 历史不变可长缓存 | 标 run_id/生成时间；离线可读 |
| K 线/key-levels | 是 | 60s–按交易日 | 非交易日按发布日，不用自然日 |
| 写操作（paper/settings/feature-flag/admin） | **否** | — | 离线**禁用**，提示"需联网"；不排队伪写 |
| 鉴权（login/refresh/me） | 否 | — | 离线不可登录；token 过期需联网刷新 |

**离线模式限制**：只读浏览 + 缓存渲染；**禁止**任何写、任何"今日最新生产结论"的强声明（必须标缓存时间与交易日发布口径）。

---

## 8. 实施路线

- **Phase 0 调研（低成本）**：度量当前云账单结构（常驻 vs 请求）、确认"降本"是否真痛点；若主体是常驻基础设施，明确客户端化目标改为 UX/离线/分发而非省云。产出决策门。
- **Phase 1 PWA（推荐起点）**：frontend-next 加 `vite-plugin-pwa` + manifest + Service Worker 静态预缓存 + 安装能力；不改后端、不改契约；仍连云端 API。验收：可安装、离线壳可开、首屏后静态走缓存。
- **Phase 2 Tauri 壳（可选/按需）**：仅当需要桌面级离线 + 本地数据库 + 本地 sidecar 计算时；复用 Rust 工具链；引入签名/自动更新通道。否则**跳过**。
- **Phase 3 本地缓存（SWR/IndexedDB）**：对第 7 节可缓存接口落 IndexedDB 持久缓存 + stale 标识；写操作离线禁用。验收：重复 GET 命中本地、离线只读可用、stale 不误导。
- **Phase 4 本地报告/回测预览**：历史报告/回测 run 的只读本地浏览与 preview 级重排/对比（非权威）；权威生成仍云端 worker。验收：preview 与云端权威结果口径一致、明确标 Preview/非事实源。

---

## 9. 验收标准

1. **功能可用**：核心闭环 `/monitor→/playbook→/backtest→/paper→/settings` 在 PWA 安装态可用；离线态只读壳可开。
2. **策略结果一致**：客户端展示的 `production_score/priority_score/signal_state/lane/日期` 与云端 API 完全一致；客户端不重算/不重排（沿用既有审计守卫）。
3. **云端请求下降**：本地缓存命中后，重复 GET（行情/榜单）请求数较基线下降（DevTools/网关指标可量化）。
4. **服务资源下降**：**诚实标注**——常驻服务（MySQL/Redis/Worker/Go）资源**不因客户端化下降**；仅 app/go-bff 请求侧 CPU 与出网带宽小幅下降。若需显著降云，走第 5 节非客户端杠杆。
5. **回滚可行**：PWA SW 版本化即时回退；旧前端 `frontend/` 保留；契约不兼容时客户端降级提示；无生产数据风险。
6. **安全**：token 不落明文、写操作离线禁用、缓存敏感数据短 TTL + 登出清除、stale/离线显式标识。

---

## 10. 明确结论

- **是否值得做**：**值得，但要校正目标**。客户端化（PWA）对**用户体验（安装、离线只读、重复加载更快）、分发、首屏后省回源**有真实价值；对**显著降低云服务器资源占用——不能**，因为云成本主体是与客户端数量无关、按硬边界必须留云的常驻基础设施（MySQL+Redis+数据刷新 Worker+Go 服务）。
- **PWA 还是 Tauri**：**先 PWA**（复用现有 SolidJS SPA、零额外运行时、维护最低、安全成熟）；**Tauri 仅按需**（桌面级离线/本地库/本地 sidecar 时再上，可复用仓库 Rust 工具链）；**Electron 不推荐**。
- **能否显著降云**：**不能（在当前少用户 + 常驻为主的成本结构下）**。客户端化只带来请求侧小幅下降。**要显著降云成本，应做**：analytics-worker 按需化（非常驻）、scheduler/worker 副本右调、进行中的产物瘦身、MySQL/Redis right-size——这些与客户端化**正交**、且 ROI 更高。
- **一句话**：**把它做成 PWA 客户端去提升体验与分发是对的；但别把它当成省云服务器的手段——省云要从 Worker 按需化和基础设施 right-size 入手。**

---

## 交付说明（合规）
- 未修改任何代码；仅新增本报告。
- 未部署、未切流、未删除旧前端、未改 `strategy_policy.py`/生产排序/`production_score`。
- 在途的"平台瘦身"删除/新增改动**未被本轮回滚**。
