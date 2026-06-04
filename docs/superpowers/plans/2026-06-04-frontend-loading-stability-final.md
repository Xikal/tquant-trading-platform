# 前端加载慢/加载失败 · 最终方案(2026-06-04)

> **For agentic workers**:REQUIRED SUB-SKILL — superpowers:executing-plans。Steps 用 `- [ ]` 跟踪。
>
> **定位(实测结论,不是估计)**:前端"加载慢 + 容易加载失败"的根因不是架构,是 **5 个具体的、已实测的工程缺口**——其中 2 个是**已规划但未落地**(BFF 合包早已在后端写好,前端没接上)。本计划只做"接到位 + 容错修齐 + 包再切一刀",**不换栈、不改业务边界、不动策略口径**。
>
> **关联**:
> - `docs/superpowers/plans/2026-06-03-monitor-priority-board-latency-final.md`(L1 BFF 合包 / L2 stale 回退 / L3 overlay 缓存 / L4 placeholderData / L5 增量物化)— 本计划继续推进 L1-L4,**不做** L5
> - `docs/superpowers/plans/2026-06-03-frontend-stability-final-hardening.md`(H1-H4 前端稳定性)— 本计划是其执行收口
> - 后端已就绪:`backend/app/api/routes/bff.py:89,121 monitor_workspace_bff`(已有 cache + overlay + remote fallback)

---

## 1. 实测真因(每条带证据)

| # | 问题 | 实测证据 | 严重度 |
|---|---|---|---|
| **B1** | TanStack Query 全局 `retry: false` → **任何抖动失败一次就直接红屏** | `frontend/src/state/queryClient.ts:10,17,35` 三处全是 `retry: false`(queries / mutations / createAppQueryClient) | 🔴 这就是"容易加载失败"的核心根因 |
| **B2** | 监控页 13 个独立 useQuery 并发(任一失败即模块空) | `frontend/src/features/trading-workspace/useMonitorData.ts:41-92` `MONITOR_SERVER_KEYS` 列 13 key:`priorityBoard / marketBreadth / marketPulse / hourlySnapshotHistory / reviewStatus / reviewReports / sectorRelativeStrength / keyLevelAlerts / watchlistSignals / sectorEtfT0 / pairedHedge / runtime / instrumentSyncStatus` | 🔴 慢 + 易失败叠加 |
| **B3** | **后端 BFF 合包已存在**,前端**0 引用** | 后端 `backend/app/api/routes/bff.py:89,121 def monitor_workspace_bff` 已实现合包 + `workspace_cache` + `apply_monitor_workspace_live_overlay`;前端 `rg "bff/v1/workspace/monitor"` 命中 0 | 🔴 现成能力没接上 |
| **B4** | 首屏关键路径 chunks 偏重 | dist 实测:`antd-core 329K + antd-check-controls 316K + antd-display 186K + react-vendor 93K + tanstack 51K`,三块 ~800K 进入首屏 | 🟡 加载慢次因 |
| **B5** | api 层有 `retryRequest` 但被顶层 `retry: false` 绕过 | `api/base.ts:50,245-258` 有重试封装,但 query 层 `retry: false` 让它形同虚设 | 🔴 与 B1 同源 |

**结论**:**B1 是"容易失败"的核心根因**(改一个常量就能极大改善);**B2+B3 是"慢"的核心**(后端合包已就绪,只差前端接上);B4 是后做的次因。

---

## 2. 明确不做(防止过度工程)

- ❌ 换 React / AntD / Vite / ECharts
- ❌ 上 SSR / RSC / WASM / 微前端
- ❌ 改业务语义、策略口径、生产门
- ❌ 替换 ECharts 或引新图表库
- ❌ 改 30s 轮询频率(改快会放大问题)
- ❌ 实现增量物化(L5,不在本期)
- ❌ 引入 WebSocket(BFF + retry 做对就不需要)
- ❌ 部署(除非用户明确要求)
- ❌ 清理或 revert 无关脏改动

---

## 3. 硬边界(实施期不可跑偏)

1. **栈冻结**:零新增 npm 依赖。
2. **服务端态唯一在 TanStack Query**;不把响应数据复制进 Zustand store。
3. **零 useState/useReducer**(沿用 `check-state-separation.mjs / check-refactor-guard.mjs`)。
4. **接口契约不动**:OpenAPI 是事实源;前端 wrapper 从 `generated/api-types.ts` 取类型。
5. **生产口径不动**:`priority_board / production_score / strategy_policy / participates_in_priority_board` 不受本计划影响。
6. **stale 标识端到端透传**(L2 已建,本计划不破坏)。
7. **接口抖动不闪空白**(`placeholderData` 已建,本计划不破坏)。
8. **每项改动可独立 flag 回退**。

---

## 4. 最终方案(4 项收尾,按 ROI 排序)

### **L1｜把全局 retry 改成"有限指数退避",立即消除"一抖即红"(最高 ROI,半天活)**

**问题**:`retry: false` 让任何抖动直接红屏。
**做什么**:
- `state/queryClient.ts:queryClientDefaults.retry`:`false` → `(failureCount, error) => failureCount < 2 && isRetryableError(error)`
- 新增 `isRetryableError(error)`:**只对网络/5xx/超时重试**;**401/403/400/404/422 不重试**(用户/认证错误立即返回);**Abort 不重试**(组件卸载)。
- 加 `retryDelay: (i) => Math.min(1000 * 2 ** i, 8000)` 指数退避(1s→2s→4s,上限 8s)。
- mutations 仍 `retry: false`(写操作不重试,避免重复)。
- 顺手把 `api/base.ts` 已存在的 `retryRequest` 与 query 层重试**统一口径**:同一类错误只重试一次,不嵌套。

**为什么是最高 ROI**:**修一个常量,改善整页"一抖即红"**;`placeholderData` 已存在(切 tab 不闪空),但失败仍是空白——这正是 L1 要补齐的最后一块。

**验收**:
- `pytest backend/tests`(走 frontend smoke):监控页 mock 单接口失败一次后重试成功,**UI 不闪红**。
- 故意 mock 401 → **不重试**直接走登录(避免重试风暴)。
- `cd frontend && npm test -- --run` 全绿。

### **L2｜接入后端已有的 BFF 合包(L1 计划的最后一公里)**

**问题**:后端 `monitor_workspace_bff`(`bff.py:89,121`)早已实现 + cache + overlay + remote fallback,**前端没用**。
**做什么**:
- 新建 `frontend/src/features/trading-workspace/useMonitorWorkspaceBff.ts`,**调用 1 个**`GET /api/bff/v1/workspace/monitor`,从合包 payload 中按字段切片暴露 13 个 selector。
- `useMonitorData.ts` 改为:**默认走** `useMonitorWorkspaceBff`,失败时按字段独立 fallback(用既有 13 个 useServerState 作降级)。
- 通过 feature flag `MONITOR_BFF_AGGREGATE_ENABLED`(默认 `true`,本期上线即开)控制;关闭即回到现状 13 个独立 query。
- 守卫断言:合包前后字段 sha256 一致(前端单测 mock 同样响应做对照)。

**为什么 ROI 高**:从 13 次 RT → 1 次 RT;后端 cache + remote fallback 已就绪,前端只是"接到位"。

**验收**:
- 浏览器 DevTools Network:监控页一次刷新只 1 个 `bff/v1/workspace/monitor` 请求(或合包失败时降级到独立 13 个)。
- 监控页 P95 较 M0 ↓≥50%(冷启)/ ↓≥30%(热)。
- 监控页字段 sha256 合包前后一致(关键字段:`priority_board.items[*].symbol/priority_score/production_score/buy_signal_state`)。
- `npm test --run` 全绿,含新 `useMonitorWorkspaceBff.test.ts`。

### **L3｜AntD 首屏切片再走一刀 + 性能预算门接入 CI**

**问题**:`antd-core 329K + antd-check-controls 316K + antd-display 186K` 仍偏重。
**做什么**:
- `vite.config.ts` 复审 manualChunks:把 `antd-check-controls`(Checkbox/Radio/Switch/Slider)拆为按需 chunk(只在用到的页面 lazy);`antd-display`(Table/List/Tree 等)同理审查是否所有首屏路径都需要(很可能监控/纸面/策略追踪是 lazy,设置/管理可以 lazy)。
- `@ant-design/icons` 按需 import(以 `frontend/src/ui/icons/index.ts` 集中索引,显式列出用到的图标 ES 路径)。
- 接入性能预算门:新建 `frontend/scripts/check-bundle-budget.mjs`,基于 `bundle-report.mjs` 输出,断言 `first_screen_js_gzip_kb ≤ 350`、单 chunk gz ≤ 150(超须 `.bundle-allowlist.json` 显式列出 + 理由)。
- `package.json` 加 `"check:bundle-budget": "node ./scripts/check-bundle-budget.mjs"`,接入 `npm run lint`。

**验收**:
- `npm run analyze` 首屏 gz 较 M0 ↓ ≥ 20%(本期目标;若做完仍未达 350KB,放下个迭代继续切)。
- CI 故意把 Detail 组件挪回首屏 → 红;恢复 → 绿。

### **L4｜全局错误兜底 + 关键页面失败 UI 一致化**

**问题**:接口失败时不同页面 UI 行为不一致(有的红,有的空)。
**做什么**:
- 新建 `frontend/src/ui/feedback/QueryErrorBoundary.tsx`:对 query error 显式标"失败 + 重试按钮 + 切到上次缓存(如 placeholderData 可用)"。
- 监控页/纸面/策略追踪/回测页统一包裹该 boundary;**boundary 只展示重试按钮,不调真实接口**(让 Query 自己重试)。
- 失败文案不出现"建议/必涨/低吸"等业务误导词(沿用既有文案守卫)。
- 接口超时 `timeoutMs` 默认值显式化(如 8s),在 `api/base.ts` 集中。

**验收**:
- 模拟接口 500 → 显示"加载失败,正在重试…",**不闪空**;重试成功后 UI 自动恢复。
- 模拟 401 → 走登录态(不进 boundary 重试循环)。

---

## 5. 落地批次与依赖

```
[L1 retry 常量改] ──┬──> [L4 错误兜底 UI]
      (半天)        │       (1 天)
                    │
[L2 BFF 合包接入] ──┘
      (1-2 天)
                    │
                    └──> [L3 AntD 切片 + 预算门]
                            (1-2 天)
```

- **L1 是其他三件的前置**(retry 改对了,L2/L4 的失败处理才有意义)。
- **L2 与 L4 可并行**(L2 是后端接入,L4 是 UI 兜底,互不依赖)。
- **L3 单独可做**,但建议放后面——L1/L2/L4 是"修体感";L3 是"压预算"。

**总工作量**:约 3-5 人日。

---

## 6. 量化验收门

| 指标 | M0 基线 | 目标 |
|---|---|---|
| 监控页"一次抖动失败导致红屏"率 | 高(retry=false 一抖即红) | **0**(L1) |
| 监控页一次刷新请求数 | 13 | **1**(L2 合包生效) |
| 监控页 P95 冷启 | 850ms+ (云报告) | ↓≥50%(L2) |
| 监控页 P95 热路径 | 受 overlay/filter 拖累 | ↓≥30%(L2) |
| 首屏 gz | 待 analyze | **↓≥20%**(L3) |
| 单 chunk gz 上限 | antd 最大 ~150KB gz | **≤150KB gz**(L3 + budget gate) |
| 接口失败 UI | 空白/红屏 | **统一"加载失败,正在重试"+ 上次缓存**(L4) |
| 关键字段 sha256(合包前后) | — | **一致**(parity 守卫) |
| 守卫测试 | 全绿 | **全绿**(`check-state-separation / check-refactor-guard / check-bundle-budget` 都通过) |

---

## 7. Verification Commands

```bash
# 后端 BFF 合包路径不变(无新改动需要)
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_bff_*.py -q 2>&1 | tail -5

# 前端门禁
cd frontend
npm run api:check
npm run lint                          # 含 check-bundle-budget (L3 后)
npm test -- --run                     # 含新 useMonitorWorkspaceBff.test.ts, QueryErrorBoundary.test.tsx
npm run build
npm run analyze                       # 看 first_screen_js_gzip_kb / Top chunks

# 浏览器实测(L2 验证)
# 进入监控页 → DevTools Network → 只 1 个 /api/bff/v1/workspace/monitor 请求
# 模拟接口失败一次 → UI 显示"加载失败,正在重试…" + 1-2 秒后自动恢复(L1+L4)
```

---

## 8. Rollback

每项独立可回退(均带 feature flag 或常量):
- **L1**:`queryClient.ts:retry` 改回 `false`(回退到 M0)。
- **L2**:`MONITOR_BFF_AGGREGATE_ENABLED=false` 回退到 13 个独立 query。
- **L3**:`vite.config.ts` 切片回退到当前 splitVendorChunks;budget gate 临时关掉。
- **L4**:`QueryErrorBoundary` 删除即回到现状(各页面自管错误)。

每项独立 PR / commit;任何一项回归即可独立回退,不互相依赖。

---

## 9. Definition Of Done

- 监控页一次刷新只 1 个 BFF 请求;
- 抖动失败一次 UI **不闪红**,自动重试 1-2 次成功;
- 首屏 gz 较 M0 ↓ ≥20%;
- 全部接口失败统一走 `QueryErrorBoundary`,不出现空白/裸红屏;
- 关键字段 sha256 合包前后一致(parity);
- `pytest backend/tests` 与 `npm test -- --run` 全绿;
- 未换 React/AntD/Vite/ECharts;未引新 npm 依赖;
- 业务语义/策略口径/生产门未受影响;
- 每项可独立 flag 回退,无 schema 变更、无数据迁移。

---

## 10. 一句话总结

**"加载慢 + 容易失败"四个根因实测到位**:**B1 retry: false(改一个常量解决"一抖即红")+ B2 监控 13 个并发(L2 接已就绪的后端 BFF 合包)+ B4 首屏 chunks 偏重(再切一刀 + 预算门)+ B5 retry 双重失效**。本计划是 3-5 人日的工程收尾,**不换栈、不改业务、不动策略**,每项独立可回退。**L1 一个常量改了就能极大改善失败率;L2 接已建好的后端合包就能极大改善慢**——这两件是必须先做的。
