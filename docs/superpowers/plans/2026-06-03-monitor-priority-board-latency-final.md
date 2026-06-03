# 实时监控榜单刷新延迟 · 根因诊断与最终优化方案 (2026-06-03)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 或 superpowers:executing-plans。Steps 用 `- [ ]` 跟踪。
>
> **定位（基于实测的最终结论）**:实时监控页"榜单刷新慢"的根因 **不是前端轮询**也**不是后端算力**——前端 query 配置已是优等(`staleTime 5s + refetchInterval 30s + refetchOnWindowFocus=false + retry=false`),后端 priority_board 路径有完整的"命中/陈旧/异步刷新"分级缓存。**真实瓶颈**是 4 件事的叠加:
> 1. **监控页一次刷新打 14+ 个独立 useQuery 接口**(MONITOR_SERVER_KEYS 列出 14 个 key),没有合包 → 串行/并发 14 次 cookie+CSP+网络往返;
> 2. **后端 `priority_board` cache miss/cache empty 走"异步队列"** → 用户看到 **`stale`/空** 榜单 + `snapshot_warning`,要等 worker 回填后下次刷新才有真数据,**首次冷启感觉极慢**;
> 3. **实时叠加 `apply_priority_board_live_overlay` 每次请求都重算**(读 `local_quote_cache` × N symbols + model_copy 整树),叠加 `filter_priority_board_response`(逐 item 过滤板块偏好) → 每次请求都重新生成响应对象,削弱了响应缓存的实际收益;
> 4. **后台物化是 60 分钟级**(`FULL_SCAN_REFRESH_SECONDS = 60*60`)+ `low_buy_materialization_refresh` 5 分钟入队,**冷启动场景下榜单实际很久才有新数据**——前端"慢"其实是"等不到"。
>
> 本计划是**最终方案**,只做端态收口,不引新框架、不上 SSR/WASM、不做 async 全量重写,不动 `portfolio_backtest_metrics` 等业务事实源。
>
> **关联文档**:`docs/superpowers/plans/2026-06-03-frontend-stability-final-hardening.md`(前端稳定性收尾)、`docs/superpowers/plans/2026-05-30-backend-performance-hardening.md`(G1/G2/G3 I/O 治理)、`docs/superpowers/plans/2026-06-03-backend-compute-acceleration-final.md`(Rust 复用、并行扫描)。本计划聚焦"监控榜单端到端延迟"的具体收尾。

---

## 1. 真实瓶颈诊断(实测,2026-06-03)

| # | 问题 | 实测证据 | 实际影响 |
|---|---|---|---|
| **D1** | 监控页一次刷新 14+ 个独立请求 | `frontend/src/features/trading-workspace/useMonitorData.ts:42-54` 定义 `MONITOR_SERVER_KEYS` 14 个 key(priorityBoard / marketBreadth / marketPulse / hourlySnapshotHistory / reviewStatus / reviewReports / sectorRelativeStrength / keyLevelAlerts / watchlistSignals / sectorEtfT0 / pairedHedge / runtime / instrumentSyncStatus + 派生) | 每 30s × 14 次 RT;任意一条慢就把榜单"等出来";HTTP/1.1 浏览器并发上限 6 加剧串行感 |
| **D2** | 后端 cache miss → 异步刷新 + 返回 stale/空 | `backend/app/services/low_buy/priority_board.py:101-118`:cache 命中直接返回(快);命中陈旧→入队后返回 `stale`;缓存空→入队后返回**空响应** + `snapshot_warning="优先榜正在后台刷新,当前暂无..."` | 冷启动/换 variant/刚部署/数据日切场景**首次返回空**,用户主观体感"榜单刷新慢/不出来";前端要再轮询才能拿到 |
| **D3** | 实时叠加每请求重建响应对象 | `backend/app/api/routes/screeners.py:166-167` 每请求顺序调用 `filter_priority_board_response`(按用户板块偏好过滤 items + 重算 immediate/focus/track counts + 重过滤 family_sections)+ `apply_priority_board_live_overlay`(读 Redis 报价覆盖 N symbols + 逐 item `model_copy`)。`live_quote_overlay.py:19-28,108-139` 每请求一次 Redis batch + 整树 copy | 即便命中响应缓存,这两步**永远跑**,延长 P50/P95;且生成新对象,响应缓存与"最终响应"不是同一对象 |
| **D4** | 物化频率与刷新窗口不匹配 | `backend/app/runtime/background_jobs.py:55,407-409` `FULL_SCAN_REFRESH_SECONDS = 60*60` 全市场扫描每小时;`:437-438` `low_buy_materialization_refresh` 每 300s 入队;`market_quote_cache_refresh` 每 30s | 用户开页后,**新数据要等 5-60 分钟才物化进缓存**,前端无论怎么刷只能拿到上一份 |
| **D5** | live overlay 命中率未对外可见,且 cookie 鉴权每请求重算 | `live_quote_overlay.py:124-139` 调用 `read_local_quote_snapshots` 一次 Redis batch + 逐 hit/miss 计数;监控页 14 个端点每个都过 `Depends(get_current_user)` 鉴权 + CSP 中间件 | 鉴权/CSP 串行打满浏览器并发额度,叠加 D1 |
| **D6** | 前端没有 SWR 占位 / 没用 stale 数据保留 | `frontend/src/features/monitor/queries.ts:12-13` `staleTime:5s, refetchInterval:30s`,但**未启** `placeholderData/keepPreviousData` | 接口抖动/慢源时,前端切 tab/换 lane 会瞬时闪空,主观"卡" |

**结论**:慢=**14 个串行请求 + 首次冷启返回空/陈旧 + 命中缓存仍每请求重算覆盖 + 物化窗口跟不上用户期待**,这四件事的叠加。不是单点。

---

## 2. 明确不做(避免负 ROI)

- ❌ 改 30s 轮询频率(改快只会放大上面 4 个问题,且与平台不实时下单定位不符)。
- ❌ 全栈 async / 换框架 / 引 WASM。
- ❌ 把 priority_board 物化频率改到分钟级(全市场 5000 标的 × 多策略,代价巨大且不必要)。
- ❌ 改 `portfolio_backtest_metrics` / `participates_in_priority_board` / 策略口径。
- ❌ 引入 WebSocket(本计划不上,因为先把 BFF/缓存层做对成本更低)。
- ❌ 把 `apply_priority_board_live_overlay` 移除(它解决"报价比物化新"的实际需求,只是要让它更轻、可被缓存)。

---

## 3. 硬边界(不可跑偏)

1. **不改业务语义/口径**:榜单内容、过滤规则、`production_score` 门均不变。
2. **不绕过用户板块偏好过滤**:`filter_priority_board_response` 逻辑保留,只允许换实现/加缓存。
3. **不破坏 priority_board 现有"命中/陈旧/异步刷新"分级**;只在边界优化。
4. **不新增 Web 后台 loop**(沿用既有规则)。
5. **零新增运行时依赖**(BFF/Redis/RuntimeTask 都已具备)。
6. **可回滚**:每项改动支持独立 feature flag 关闭。

---

## 4. 最终方案(5 项收尾,按 ROI 排序)

### **L1｜BFF 监控工作台单接口合包(最高 ROI)**

**问题**:14 个独立 useQuery 接口 → 14 次鉴权/CSP/RT。
**做什么**:监控页一次刷新走**1 个 BFF 接口**返回完整 workspace payload。
- 后端:监控 workspace 聚合接口**已存在并已有缓存**——`backend/app/services/bff/workspace_cache.py` 和 Go bff-gateway(`tquant_bff_workspace_cache_*` metrics 已暴露,`bff_monitor_cache_ttl_seconds=5` 在 config 默认配置)。**关键动作**:把前端 `useMonitorData.ts` 14 个 useQuery 整体替换为**一个**对 `/api/bff/v1/workspace/monitor` 的 query,后端聚合返回 priority_board + market_breadth + market_pulse + key_level_alerts + watchlist_signals + ... 等。
- 前端:保留 14 个 `useQuery` selector(从合并 payload 里 `select` 各自切片),网络层只 1 次往返。
- Live overlay:`apply_monitor_workspace_live_overlay`(`live_quote_overlay.py:39-50`)**已实现**,直接复用。
- **预计**:监控页 TTFB 从"14 次 RT 中最慢一条"降到"1 次 RT",P95 显著下降。

### **L2｜priority_board 缓存空时返回上次可用快照而非空响应**

**问题**:cache empty + 入队后端 → 前端拿到空响应 + 警告 → 用户"刷不出"。
**做什么**:`priority_board.py:113-118` 的 `_empty_priority_board_response` 改为:
- 优先从**长 TTL 持久层(SystemSetting/analytics)** 读取"上次成功的榜单快照",若有则返回带 `snapshot_warning="正在后台刷新,当前展示上次可用榜单"` 的版本(`data_quality=stale`);
- **只有从未生成过任何快照**才返回空响应。

效果:用户冷启/换 variant/刚部署也能立即看到内容,**而不是空白等 5 分钟**。

### **L3｜把 live overlay + sector 偏好过滤的结果也加入缓存**

**问题**:`screeners.py:166-167` 每请求都顺序跑 `filter_priority_board_response` + `apply_priority_board_live_overlay`,即便命中响应缓存,这两步永远跑。
**做什么**:
- live overlay 缓存(短 TTL 1-3s):缓存键 `priority_board:{cache_key}:overlay`,内容是叠加后的对象;键随 `local_quote_cache` 的 `version`/`as_of` 失效。
- 板块偏好过滤缓存(per-user,短 TTL 30s):键 `priority_board:{cache_key}:user={user_id}:excluded_hash={hash}`。
- 应急 flag:`READ_MODEL_LIVE_OVERLAY_ENABLED=false` 已存在,可关闭叠加(应急回退)。

效果:命中缓存路径**真正命中到最终对象**,免去每请求约 N×Redis_read + 整树 model_copy。

### **L4｜前端 useQuery 加 `placeholderData` + 错峰**

**问题**:抖动/慢源时切 tab 闪空白;14 个 query 同一时刻同时 fetch。
**做什么**:
- `MonitorQueries.queries.ts` 等所有热查询统一加 `placeholderData: (prev) => prev`(等效 `keepPreviousData:true`)——抖动时保留上次数据,不闪空。
- 错峰:`useMonitorData.ts` 14 个 query 的 `refetchInterval` 不能都同时打 → 在 L1 合包后这个问题自动消失;若 L1 推迟,临时做法是按 key 分桶错峰(`refetchInterval` 各加 0/2/5/8/12s 偏移)。

### **L5｜后台物化窗口与用户感知对齐**

**问题**:全市场扫描 60 分钟、materialization_refresh 5 分钟,与"刷新榜单"的用户预期(30 秒~分钟级)不对齐。
**做什么**(**最小化、不大改**):
- **不改全市场扫描频率**(代价高);
- **增**:`market_quote_cache_refresh` 已 30s 在跑,**确保 live overlay 真正消费它**(L3 已做);
- **物化触发器**:在 `_enqueue_priority_refresh` 已有的"异步刷新"链路上,如果上次入队距今 > 60s 才再入队(避免重复入队),并把 worker 端做轻量"增量物化"(只对受 cache_key 影响的 strategy 跑,不必每次全市场扫)——若代价不可控,本步骤可推后,**L1+L2+L3 已经能解决主要主观慢**。

---

## 5. 落地批次与验收

| 批 | 内容 | 工作量 | 验收 |
|---|---|---|---|
| **L1** BFF 合包(替换 useMonitorData 14 个 query) | 1-2 天 | 监控页 Network 面板:一次刷新只有 1 个对 `/api/bff/v1/workspace/monitor` 的请求;TTFB 显著下降 |
| **L2** 空响应回退到上次快照 | 0.5 天 | 冷启动场景立即看到上次榜单 + `data_quality=stale` + 警告;不再空白 |
| **L3** Overlay + 偏好过滤结果缓存 | 0.5-1 天 | `apply_priority_board_live_overlay` 命中缓存路径耗时 ≈ 0;`/metrics live_overlay_*` 命中率上升 |
| **L4** 前端 placeholderData | 0.5 天 | 切 tab/换 lane 不闪空白;`pytest` 与 `vitest` 全绿 |
| **L5** (可选)物化触发器 | 0.5 天 | 入队不重复;worker 日志看到增量物化 |

**总工作量约 3-4 天**,前端不换栈,后端不重构。

---

## 6. 量化验收门(M0 基线对比)

| 指标 | M0(实测前) | 目标 |
|---|---|---|
| 监控页一次刷新请求数 | 14+ | 1(L1 后) |
| 监控页 P95(冷启) | 受最慢一条接口拖累 | 下降 ≥50%(L1+L2) |
| 监控页 P95(热路径,命中缓存) | 受 overlay+filter 拖累 | 下降 ≥30%(L3) |
| 冷启榜单空响应率 | 高(变种/数据切换时) | 0(L2) |
| 切 tab 闪空白 | 有 | 无(L4) |
| `pytest backend/tests` | 全绿 | 全绿 |
| `npm run lint && npm run build && npm test --run && npm run api:check && npm run analyze` | 全绿 | 全绿 |
| 接口 `priority_board` 数值/口径 | 基线 | 1e-9 一致(parity) |

---

## 7. Verification Commands

```bash
# 后端
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py -q
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q

# 前端
cd frontend && npm run api:check && npm run lint && npm test -- --run && npm run build && npm run analyze

# 接口实测(开浏览器 DevTools Network 面板)
# 1. 监控页打开 → 期待 L1 后只有 1 个 /api/bff/v1/workspace/monitor 请求
# 2. 冷启/切 variant → 期待 L2 后不再返回空响应
# 3. 连续两次同 cache_key 调用 → 期待 L3 后第二次耗时显著低于第一次
```

---

## 8. Rollback

每项独立可回退(feature flag):
- L1:`MONITOR_BFF_AGGREGATE_ENABLED=false` 回到 14 个独立 query。
- L2:`PRIORITY_BOARD_EMPTY_FALLBACK_TO_LAST_SNAPSHOT=false` 回到空响应。
- L3:`READ_MODEL_LIVE_OVERLAY_ENABLED=false`(已存在)关闭叠加;`PRIORITY_BOARD_OVERLAY_CACHE_ENABLED=false` 关叠加结果缓存。
- L4:前端 `placeholderData` 删除即回退,无 schema 变更。
- L5:不入队增量物化 = 沿用原 5 分钟入队。

---

## 9. Definition Of Done

- 监控页一次刷新只有 **1 个**网络请求(L1);
- 冷启/换 variant 立即看到内容,**不再空响应**(L2);
- 命中缓存路径**不再重算 overlay/filter**(L3);
- 切 tab/换 lane **不闪空白**(L4);
- 数据口径 1e-9 一致;`pytest` 全绿;前端 `lint/build/test/api:check/analyze` 全绿;
- 监控页 P95 较 M0 下降 ≥50%(冷启)/ ≥30%(热);
- 每项改动可独立 flag 回退。

---

## 9.1 对策略结果正确性的影响逐项分析(2026-06-03 补充)

**总结论:本方案不动策略计算路径(`low_buy_screener.priority_board → _build_priority_items → production_scoring → portfolio_backtest_metrics`)**,只动展示层/网络层/响应缓存层。逐项:

| 项 | 是否影响策略结果 | 风险点 | 守卫机制 |
|---|---|---|---|
| L1 BFF 合包 | **不影响**,反而跨端点一致性更好 | 14 子端点合包后 `data_quality/stale` 标识不能被洗掉 | 端到端测试 stale 字段透传;复用 `apply_monitor_workspace_live_overlay` 范式 |
| L2 冷启返回上次快照 | **不影响** | `data_quality=stale` 必须端到端传到 UI 显式提示 | UI 文案守卫 + 端到端测试 "stale 标识可见" |
| L3a Live overlay 缓存(1-3s) | **不影响**(overlay 不参与评分/排序/buy_now 判定) | 缓存 key 必须含 `local_quote_cache.version/as_of`,版本变化失效 | 单测 + parity 测试:同输入下"启用 overlay 缓存"与"禁用"返回相同字段值 |
| L3b 板块偏好过滤缓存(per-user 30s) | **不影响策略本身;影响用户偏好实时性** | 用户改偏好后 30s 内仍看到旧过滤结果 | **必须加**:`UserSectorPreferenceService.update_*` 后主动 `invalidate("priority_board:*:user={user_id}:*")`;缓存 key 含 `excluded_hash` 双保险;端到端测试 `test_priority_board_filter_cache_invalidates_on_user_preference_change` |
| L4 前端 placeholderData | **不影响** | 抖动时仍是上次真实后端数据 | 与 L2 stale 标识协同 |
| L5 增量物化触发(可选) | **可能影响**(增量范围划定不全→排序漂移) | 必须 parity 测试守护;**不做就 100% 安全** | `test_incremental_vs_full_materialization_parity`;失败立即回退;**推荐先不做** |

**实施建议**:**只做 L1+L2+L3+L4,推迟 L5**。这四项已能把主观"刷不出来"解决到端态,且**完全不动策略路径**;L5 仅在 P95 仍未达标时再评估,且必须 parity 守护后才合入。

**策略稳定性保护清单(发布前必跑)**:
- [ ] `pytest backend/tests/test_low_buy_priority_board_strategy_variants.py` 全绿(口径未变)
- [ ] `pytest backend/tests/test_low_buy_production_scoring.py` 全绿(production_score 未漂移)
- [ ] 新增 `test_priority_board_overlay_cache_returns_same_payload_as_uncached`(parity)
- [ ] 新增 `test_priority_board_filter_cache_invalidates_on_user_preference_change`(L3b 守卫)
- [ ] 新增 `test_priority_board_empty_falls_back_to_last_snapshot_with_stale_flag`(L2)
- [ ] 接口实测:L1 合包前后,`/api/screeners/low-buy/priority-board` 返回的 items 顺序、`production_score`、`priority_score`、`buy_signal_state`、`elite_watch_score` 等关键字段**完全一致**(取 sha256 对比)
- [ ] 不出现:已退出生产的 N 字策略的 `buy_now`/`soft_buy_now`(沿用既有守卫)

---

## 10. 一句话总结

**监控页"刷新慢"的真因不是单点,而是"14 个串行请求 + 首次冷启返回空 + 命中缓存仍每请求重算覆盖"的叠加**。最终方案是 5 项小收尾:**BFF 合包 + 空响应回退快照 + Overlay/过滤结果缓存 + 前端 placeholderData + (可选)增量物化**——3-4 天工作量,不换栈、不动业务,P95 显著下降,UI 不闪。
