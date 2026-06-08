# frontend-next 再审查报告（2026-06-07）

> 性质：**只读再审查，未修改任何代码，未部署，未切流**。
> 触发：用户声明"优化方案问题已全部修改"，对照 `frontend-next-optimization-plan-2026-06-07.md` 的 O1–O10 逐项复核。
> 基线：`frontend-next-full-audit-2026-06-07.md` + 该优化方案的 M0 实测数值。
> 方法：本轮全部命令新跑；运行时类（perf:compare / screenshot:parity）因本地后端未启动（`ECONNREFUSED 127.0.0.1:8000`）无法采集，相关项标注"待后端复测"。

---

## 0. 总体结论

**Approve（功能/质量优化）+ Request changes（体积优化）。**

- **高 ROI 功能/质量项已落地**且工程门禁全绿、硬边界零破坏 —— 可合入。
- **体积优化三项（O3 体积 / O4 echarts / O5 首屏块）未达标甚至反增** —— 与"全部完成"的说法不符，若为本轮目标需补做。
- **O1/O2 的运行时数值（请求 9→? / DOM 403→?）本轮无法实测**（后端未起），源码已确认接好，需后端启动后跑 `perf:compare` 坐实。

---

## 1. 工程门禁（本轮新跑，全绿）

| 命令 | 结果 | vs 上次 |
|---|---|---|
| `npm run api:check` | ✅ 通过 | — |
| `npm run typecheck` | ✅ `tsc -b` 无错 | — |
| `npm run lint` | ✅ 通过（boundary/css/refactor/bundle-budget guard 全绿） | — |
| `npm test -- --run` | ✅ **92 passed** | 83 → 92（**+9**） |
| `npm run build` | ✅ 通过 | bundle 1,218,491 B < 1.25MB |
| `npm run e2e` | ✅ **46 passed** | 35 → 46（**+11**） |
| `node scripts/check-boundary-guard.mjs` | ✅ Boundary guard passed | worker/kline/strategy_policy 边界仍绿 |
| `perf:compare` | ⚠️ 无法采集（后端 `ECONNREFUSED :8000`） | 待复测 |
| `screenshot:parity` | ⚠️ 依赖后端数据，本轮跳过 | 待复测 |

---

## 2. 硬边界（全部成立）

| 项 | 结论 | 证据 |
|---|---|---|
| 旧 `frontend/` 未改 | ✅ | `git diff -- frontend` = 0 行 |
| 后端未改 | ✅ | `git diff -- backend` = 0 行 |
| git scope | ✅ | 仅 `frontend-next/` + `docs/` untracked |
| Worker / K 线 / strategy_policy 边界 | ✅ | `check-boundary-guard` 通过 |
| 契约优先 | ✅ | `types.ts` 仍 `ApiGet<>` 派生（80 行） |

---

## 3. 优化项逐项复核（实测 before → after）

| 项 | 目标 | before | after | 证据 | 状态 |
|---|---|---:|---:|---|:--:|
| **O1** strategy-tracking 合包 | 9→≤2 请求 | 9 | 源码已接 | `StrategyTrackingPage.tsx:78 operationQuery("strategyWorkspace")` → `operations.ts:65 /api/bff/v1/workspace/strategy` | ✅ 源码 / ⏳ 运行时待测 |
| **O2** paper 虚拟化 | DOM 403→<150 | 403 | 源码已接 | `PaperPage.tsx:289 <VirtualList>`（持仓列表）、`paper-page.css:493 .paper-console-positions--virtual` | ✅ 源码 / ⏳ 运行时待测 |
| **O6** 删 DataGrid 别名 | 删除 | 存在 | 已删 | `src/shared/ui/DataGrid.tsx` 不存在，无残留引用 | ✅ |
| **O8** 测试覆盖 | 补功能级 | unit 83 / e2e 35 | unit 92 / e2e 46 | vitest / playwright | ✅ |
| **O3-a** `!important` | 51→≤25 | 51 | **23** | `grep -rn --include='*.css' '!important' src` | ✅ |
| **O3-b** CSS 体积 | 233→≤180KB | 233 KB | **235 KB** | `cat dist/assets/*.css \| wc -c` | ❌ 未达标（持平） |
| **O4** echarts 收敛 | ↓ | 447 KB | **447 KB** | `dist/assets/echarts-*.js` | ❌ 未做 |
| **O5** 首屏块 | tanstack↓ / 首屏≤350 | tanstack 159 KB | **177 KB** | `dist/assets/tanstack-*.js` | ❌ 反增 |

### dist 体积总账（apples-to-apples）

| 指标 | before | after | Δ |
|---|---:|---:|---:|
| JS raw | 1162 KB | 1190 KB | +28 KB |
| JS gzip | 380 KB | 388 KB | +8 KB |
| CSS | 233 KB | 235 KB | +2 KB |
| echarts | 447 KB | 447 KB | 0 |
| tanstack | 159 KB | 177 KB | +18 KB |
| bundle total | 1,189,691 B | 1,218,491 B | +28.8 KB（仍 < 1.25MB） |

---

## 4. 诚实判读

**"全部完成"只对了一半。**

**✅ 已落地（高 ROI 功能/质量，当初标 P1 的核心项）**
- O1 strategy-tracking BFF 合包（源码已从多请求改走 `strategyWorkspace` 单合包）。
- O2 paper 持仓列表虚拟化。
- O6 删冗余 `DataGrid` 别名。
- O8 测试 +20（unit +9 / e2e +11）。
- O3-a `!important` 51→23。

**❌ 未达标 / 反增（体积类三项）**
- **O3-b CSS 体积**：dist 233→235KB，基本持平，**未做 PurgeCSS/合并瘦身**（目标 ≤180KB 未达）。
- **O4 echarts**：447KB 完全未变，**未做 tree-shake/收敛**。
- **O5 首屏块**：tanstack 159→177KB **反增 +18KB** —— 大概率是 O2 虚拟化引入 `solid-virtual` 的代价（DOM↓ 换 JS +18KB，属合理取舍），但 O5"缩首屏"的目标因此**没实现**；首屏未变小反变大。
- 净 bundle +29KB（仍在预算内，但方向与"瘦身"相反）。

---

## 5. 本轮未能确认（需后端启动后复测）

| 项 | 原因 | 复测命令 |
|---|---|---|
| O1 请求数 9→? | `perf:compare` 后端 `ECONNREFUSED :8000` | 启动后端后 `npm run perf:compare` |
| O2 paper DOM 403→? | 同上 | 同上 |
| 视觉 parity 8/9 是否回退 | `screenshot:parity` 需后端数据 | 启动后端后 `npm run screenshot:parity` |

> 源码已确认 O1 合包、O2 虚拟化接好，强烈指示运行时会改善，但**确切数值未经实测，不写成确定结论**。

---

## 6. 建议下一步

1. **启动本地后端 → 跑 `perf:compare` + `screenshot:parity`**：坐实 O1（请求 9→2）、O2（DOM 403→<150）、视觉不回退 —— 这是验证本轮最高 ROI 改动是否真生效的唯一硬证据。
2. **补做体积三项（若为本轮目标）**：
   - O3：PurgeCSS 扫死规则 + paper/strategy/backtest 双源合并 + login 5 文件合并（目标 dist CSS ≤180KB）。
   - O4：echarts 只 import 用到的 series/component（`echarts/core` 注册式），潜在 −100KB。
   - O5：`solid-virtual` 仅在用虚拟化的页 lazy，把它从首屏 tanstack 块拆出，抵消 O2 的 +18KB。
3. 体积三项完成后，bundle budget 应回到 < 1.19MB 并使首屏 raw ≤ 350KB。

---

## 7. 平台影响

**不影响。** 本轮仅再审查 + 新增本报告；旧 `frontend/`、后端、`strategy_policy.py` 0 改动；新前端仍挂 `/next/*`、未部署未切流；worker/kline/生产排序边界 guard 全绿。

---

## 8. 结论

- **可合入**：功能/质量优化合格，门禁全绿，边界零破坏。
- **未完成**：体积优化三项（O3 体积 / O4 echarts / O5 首屏）实际未落地，与"全部完成"不符，需补做。
- **待证**：O1/O2 运行时数值需后端起来后实测。
