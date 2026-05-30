# 前排独立策略分栏前端开发计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `front_row_weighted` 与 `front_row_only` 做成不与旧低吸策略混淆的独立前端策略线：旧策略继续保留，前排加权用于 Shadow/Paper 候选验证，前排极精选用于强前排观察提醒。

**Architecture:** 后端在低吸优先榜和策略跟踪返回中显式输出 `strategy_variant / strategy_role / display_lane`，前端按 lane 展示三条独立视图，并用状态标签说明是否可生产、是否 Paper、是否仅观察。旧排序不被替换；`front_row_only` 不生成生产排序分，只生成观察分或极精选分。

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic、React + TypeScript + Ant Design、pytest、Vitest/React Testing Library、现有低吸优先榜、策略跟踪、移动端低吸卡片。

---

## 1. 背景与结论

当前已有三种低吸候选口径：

| 口径 | 当前定位 | 主要问题 | 本计划定位 |
|---|---|---|---|
| `baseline` / 旧低吸策略 | 当前生产基准和原低吸榜 | 信号多，质量一般 | 保持原入口、原排序、原统计 |
| `front_row_weighted` | 前排加权、后排降权、极端后排剔除 | 回测明显改善，但 OOS、walk-forward、可成交性未通过 | 独立“前排加权”策略线，只做 Shadow/Paper |
| `front_row_only` | 只保留前排票的硬过滤对照组 | 样本过少、最长无票风险，不适合作为生产硬过滤 | 独立“前排极精选”雷达，只做观察提醒 |

本计划不改变生产排序，不部署，不自动开启小流量生产观察。目标是让用户在前端清晰看到三条策略各司其职，避免把 `front_row_only` 误认为生产方案，也避免 `front_row_weighted` 与旧策略混在同一榜单里。

---

## 2. 必须遵守的业务约束

1. `baseline` 旧低吸策略继续作为原生产观察/历史基准，默认排序不变。
2. `front_row_weighted` 只能作为 Shadow/Paper 候选展示，不能替换旧生产排序。
3. `front_row_only` 只能作为极精选观察雷达，不允许作为生产硬过滤方案。
4. `front_row_only` 不允许生成 `production_score`；最多生成 `watch_score` 或 `elite_watch_score`。
5. `front_row_weighted` 可以展示 `production_score`，但前端必须标明是 `Shadow/Paper` 分，不是已上线生产排序。
6. `near_entry` 仍然只能进入观察池，`production_score` 必须为 `null`。
7. 三条策略线在前端需要独立统计、独立筛选、独立说明，不把收益和信号混为一个口径。
8. 若同一股票同时命中多条策略，不在同一视图重复展示；需要展示“同时命中”标签。
9. 页面必须展示 readiness 状态：OOS、walk-forward、分钟/逐笔可成交性、弱市压缩、小流量观察建议。
10. 本轮只做前端展示与 API 结构支持，不部署、不替换生产排序。

---

## 3. 用户视角设计

### 3.1 低吸优先榜顶部策略切换

低吸优先榜增加三段式视图：

```text
原低吸策略 | 前排加权 | 前排极精选
```

每个视图的含义：

| Tab | 展示内容 | 排序依据 | 交易含义 |
|---|---|---|---|
| 原低吸策略 | 当前原低吸优先榜 | 原 `priority_score` | 保持现有生产观察逻辑 |
| 前排加权 | `front_row_weighted` 结果 | `production_score` Shadow/Paper 分 | 只用于 Paper 验证，不影响生产 |
| 前排极精选 | `front_row_only` 结果 | `watch_score` / `elite_watch_score` | 强前排雷达，只提醒观察 |

### 3.2 三列看板可作为桌面增强

如果现有页面空间允许，桌面端可增加三列看板：

```text
原低吸池           前排加权池              前排极精选池
旧生产排序         Shadow/Paper 排序       强前排观察提醒
```

移动端不强制三列，使用 tabs 或横向 segmented control。

### 3.3 页面状态文案

`front_row_weighted` 顶部状态：

```text
当前状态：只做验证，暂不影响真实排序
验证方式：影子验证 + 模拟盘验证
生产排序：没有替换旧策略
样本外验证：还不够 60 个交易日，暂未通过
滚动验证：表现还不稳定，暂未通过
可成交性：分钟/逐笔数据不足，暂未通过
小流量观察：暂不建议
```

`front_row_only` 顶部状态：

```text
当前状态：极精选观察池
用途：强前排提醒
生产排序：不参与
风险：信号很少，可能连续多天没有票
```

### 3.4 易懂提示文案规范

前端提示信息必须先说结论，再解释原因。不要只展示英文缩写或内部术语。

| 不推荐文案 | 推荐文案 |
|---|---|
| `Shadow/Paper only` | 只做验证，暂不影响真实排序 |
| `OOS 未通过` | 样本外验证还不够 60 个交易日，暂未通过 |
| `walk-forward failed` | 滚动验证表现不稳定，暂未通过 |
| `tick data insufficient` | 逐笔成交数据不足，暂不能用于真实交易判断 |
| `minute coverage below 95%` | 分钟行情覆盖不足，暂无法确认能否按计划买到 |
| `front_row_only not production filter` | 前排极精选只做提醒，不作为生产硬过滤 |
| `production_sort_replaced=false` | 没有替换旧策略排序 |
| `near_entry watch only` | 接近买点只提醒观察，不能进入生产买入排行 |

文案格式统一为：

```text
结论：暂不建议小流量观察
原因：样本外验证不足、滚动验证不稳定、成交数据不足
下一步：继续影子验证和模拟盘观察
```

其中专业词需要按以下方式解释：

| 专业词 | 页面解释 |
|---|---|
| 影子验证 | 只记录模型结果，不影响页面原排序 |
| 模拟盘验证 | 只在模拟组合里观察，不真实买入 |
| 样本外验证 | 用冻结日期之后的新数据验证，防止只适配旧行情 |
| 滚动验证 | 按时间一段一段验证，看策略是否稳定 |
| 可成交性 | 检查信号出现时，真实盘口是否可能买到 |
| 小流量观察 | 只给少量真实观察入口，不等于正式上线 |

---

## 4. 后端数据合同

### 4.1 新增枚举

新增文件：

- `backend/app/services/low_buy/strategy_lanes.py`

建议定义：

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StrategyVariant = Literal["baseline", "front_row_weighted", "front_row_only"]
StrategyRole = Literal["production_baseline", "shadow_paper_candidate", "elite_watch"]
DisplayLane = Literal["baseline", "front_row_weighted", "front_row_only"]


@dataclass(frozen=True)
class StrategyLaneDefinition:
    variant: StrategyVariant
    role: StrategyRole
    display_lane: DisplayLane
    title: str
    subtitle: str
    production_sort_replaced: bool
    production_enabled: bool
    paper_enabled: bool
    watch_only: bool


LANES: dict[str, StrategyLaneDefinition] = {
    "baseline": StrategyLaneDefinition(
        variant="baseline",
        role="production_baseline",
        display_lane="baseline",
        title="原低吸策略",
        subtitle="当前生产观察基准，保持旧排序",
        production_sort_replaced=False,
        production_enabled=True,
        paper_enabled=False,
        watch_only=False,
    ),
    "front_row_weighted": StrategyLaneDefinition(
        variant="front_row_weighted",
        role="shadow_paper_candidate",
        display_lane="front_row_weighted",
        title="前排加权",
        subtitle="前排加权、后排降权，Shadow/Paper 验证中",
        production_sort_replaced=False,
        production_enabled=False,
        paper_enabled=True,
        watch_only=False,
    ),
    "front_row_only": StrategyLaneDefinition(
        variant="front_row_only",
        role="elite_watch",
        display_lane="front_row_only",
        title="前排极精选",
        subtitle="强前排雷达，仅观察提醒，不做生产硬过滤",
        production_sort_replaced=False,
        production_enabled=False,
        paper_enabled=False,
        watch_only=True,
    ),
}
```

### 4.2 Candidate / Priority Board 字段

修改：

- `backend/app/models/schema_defs/screener_parts/candidate.py`
- `backend/app/models/schema_defs/screener_parts/priority.py`

在 `LowBuyCandidateOut` 与 `LowBuyPriorityBoardItemOut` 增加：

```python
strategy_variant: str = "baseline"
strategy_role: str = "production_baseline"
display_lane: str = "baseline"
display_lane_title: str = "原低吸策略"
display_lane_subtitle: str = ""
production_sort_replaced: bool = False
production_enabled: bool = True
paper_enabled: bool = False
watch_only: bool = False
matched_strategy_variants: list[str] = Field(default_factory=list)
primary_lane_reason: str = ""
elite_watch_score: Optional[float] = None
readiness_status: str = ""
readiness_blockers: list[str] = Field(default_factory=list)
```

字段语义：

| 字段 | 含义 |
|---|---|
| `strategy_variant` | 当前候选属于哪个策略变体 |
| `strategy_role` | 生产基准、Shadow/Paper 候选、极精选观察 |
| `display_lane` | 前端分栏归属 |
| `production_sort_replaced` | 必须为 `false`，表示未替换生产排序 |
| `production_enabled` | 只有旧策略可为 `true` |
| `paper_enabled` | `front_row_weighted` 可为 `true` |
| `watch_only` | `front_row_only` 必须为 `true` |
| `matched_strategy_variants` | 同票同时命中的策略列表 |
| `elite_watch_score` | `front_row_only` 展示用分数，不参与生产 |
| `readiness_blockers` | OOS、walk-forward、可成交性等阻断项 |

### 4.3 Priority Board Response 字段

修改：

- `backend/app/models/schema_defs/screener_parts/priority.py`

新增：

```python
strategy_variant: str = "baseline"
display_lane: str = "baseline"
display_lane_title: str = "原低吸策略"
display_lane_subtitle: str = ""
production_sort_replaced: bool = False
lane_summary: dict[str, object] = Field(default_factory=dict)
available_lanes: list[dict[str, object]] = Field(default_factory=list)
readiness_summary: dict[str, object] = Field(default_factory=dict)
```

`available_lanes` 示例：

```json
[
  {
    "display_lane": "baseline",
    "title": "原低吸策略",
    "role": "production_baseline",
    "production_enabled": true,
    "paper_enabled": false,
    "watch_only": false
  },
  {
    "display_lane": "front_row_weighted",
    "title": "前排加权",
    "role": "shadow_paper_candidate",
    "production_enabled": false,
    "paper_enabled": true,
    "watch_only": false
  },
  {
    "display_lane": "front_row_only",
    "title": "前排极精选",
    "role": "elite_watch",
    "production_enabled": false,
    "paper_enabled": false,
    "watch_only": true
  }
]
```

### 4.4 API 参数

当前接口：

- `GET /screeners/low-buy/priority-board?front_row_only=true`

建议改为兼容式新参数：

```text
GET /screeners/low-buy/priority-board?strategy_variant=baseline
GET /screeners/low-buy/priority-board?strategy_variant=front_row_weighted
GET /screeners/low-buy/priority-board?strategy_variant=front_row_only
```

保留 `front_row_only=true` 作为兼容入口，但内部映射为 `strategy_variant=front_row_only`。

修改：

- `backend/app/api/routes/screeners.py`
- `backend/app/services/low_buy_screener.py`
- `backend/app/services/low_buy/priority_board.py`
- `backend/app/services/low_buy/priority_items.py`

路由建议：

```python
@router.get("/low-buy/priority-board")
def low_buy_priority_board_view(
    limit: int = Query(12, ge=3, le=30),
    refresh: str = Query("cache", pattern="^(cache|async|sync)$"),
    strategy_variant: str = Query("baseline", pattern="^(baseline|front_row_weighted|front_row_only)$"),
    front_row_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if front_row_only:
        strategy_variant = "front_row_only"
    result = low_buy_screener.priority_board(
        db=db,
        limit=limit,
        refresh_mode=refresh,
        strategy_variant=strategy_variant,
    )
```

---

## 5. 排序与去重规则

### 5.1 各 lane 排序

| Lane | 排序字段 | 备注 |
|---|---|---|
| `baseline` | `priority_score` | 完全保持旧逻辑 |
| `front_row_weighted` | `production_score desc, priority_score desc` | `production_score` 是 Shadow/Paper 分 |
| `front_row_only` | `elite_watch_score desc, watch_score desc, priority_score desc` | 不使用 `production_score` |

### 5.2 同票多策略命中

同一股票可能同时命中旧策略、前排加权、前排极精选。前端不在同一 lane 重复展示，但需要显示标签：

```text
同时命中：原低吸 / 前排加权 / 前排极精选
```

主归属优先级：

```text
front_row_only -> front_row_weighted -> baseline
```

原因：

1. `front_row_only` 信号最少，作为强前排提醒优先被用户看到。
2. `front_row_weighted` 是当前重点验证方案。
3. 其余进入旧低吸策略。

注意：主归属只影响前端去重展示，不改变旧生产排序。

---

## 6. 前端改造

### 6.1 类型定义

修改：

- `frontend/src/types.ts`

在 `LowBuyCandidate`、`LowBuyPriorityBoardItem`、`LowBuyPriorityBoardResult` 增加与后端一致的字段：

```ts
export type StrategyVariant = "baseline" | "front_row_weighted" | "front_row_only";
export type StrategyRole = "production_baseline" | "shadow_paper_candidate" | "elite_watch";
export type DisplayLane = "baseline" | "front_row_weighted" | "front_row_only";

export interface StrategyLaneMeta {
  display_lane: DisplayLane;
  title: string;
  role: StrategyRole;
  subtitle?: string;
  production_enabled: boolean;
  paper_enabled: boolean;
  watch_only: boolean;
  production_sort_replaced: boolean;
}
```

候选项新增：

```ts
strategy_variant?: StrategyVariant;
strategy_role?: StrategyRole;
display_lane?: DisplayLane;
display_lane_title?: string;
display_lane_subtitle?: string;
production_sort_replaced?: boolean;
production_enabled?: boolean;
paper_enabled?: boolean;
watch_only?: boolean;
matched_strategy_variants?: StrategyVariant[];
primary_lane_reason?: string;
elite_watch_score?: number | null;
readiness_status?: string;
readiness_blockers?: string[];
```

### 6.2 API Client

修改：

- `frontend/src/api/appClient.ts`
- `frontend/src/api/client.ts`

新增参数：

```ts
getLowBuyPriorityBoard: (
  limit = 12,
  refresh: "cache" | "async" | "sync" = "cache",
  strategyVariant: StrategyVariant = "baseline"
) =>
  requestCached<LowBuyPriorityBoardResult>(
    `/screeners/low-buy/priority-board?limit=${limit}&refresh=${refresh}&strategy_variant=${strategyVariant}`,
    12000
  )
```

如果当前代码没有独立 `getLowBuyPriorityBoard`，则在已有加载 priority board 的地方增加 `strategy_variant` query。

### 6.3 低吸优先榜页面

优先改造位置：

- `frontend/src/features/monitor/MonitorPage.tsx`
- `frontend/src/mobile/MobileTabSections.tsx`
- `frontend/src/mobile/MobileDesignCards.tsx`
- `frontend/src/features/app-preview/portfolio.tsx`

新增组件：

- `frontend/src/features/low-buy/StrategyLaneTabs.tsx`
- `frontend/src/features/low-buy/StrategyLaneStatusCard.tsx`
- `frontend/src/features/low-buy/StrategyLaneCandidateCard.tsx`

`StrategyLaneTabs.tsx`：

```tsx
import { Segmented } from "antd";
import type { DisplayLane } from "../../types";

interface StrategyLaneTabsProps {
  value: DisplayLane;
  onChange: (value: DisplayLane) => void;
}

const OPTIONS = [
  { label: "原低吸策略", value: "baseline" },
  { label: "前排加权", value: "front_row_weighted" },
  { label: "前排极精选", value: "front_row_only" },
];

export function StrategyLaneTabs({ value, onChange }: StrategyLaneTabsProps) {
  return (
    <Segmented
      value={value}
      options={OPTIONS}
      onChange={(next) => onChange(next as DisplayLane)}
    />
  );
}
```

`StrategyLaneStatusCard.tsx` 展示：

| Lane | 必须展示 |
|---|---|
| baseline | “当前原低吸排序，保持旧逻辑” |
| front_row_weighted | “Shadow/Paper 验证中，未替换生产排序” |
| front_row_only | “极精选观察池，不参与生产排序” |

### 6.4 候选卡片

每张卡片需要展示：

1. 策略 lane 标签。
2. `production_score` 或 `watch_score`。
3. `front_row_tier`。
4. `warning_tags`。
5. `exclusion_reasons`。
6. `matched_strategy_variants`。
7. readiness 阻断项。

展示规则：

```ts
function scoreLabel(item: LowBuyPriorityBoardItem): string {
  if (item.display_lane === "front_row_only") {
    return item.elite_watch_score != null
      ? `极精选 ${item.elite_watch_score.toFixed(1)}`
      : item.watch_score != null
        ? `观察 ${item.watch_score.toFixed(1)}`
        : "观察";
  }
  if (item.display_lane === "front_row_weighted") {
    return item.production_score != null
      ? `Shadow ${item.production_score.toFixed(1)}`
      : "Shadow --";
  }
  return `优先 ${item.priority_score.toFixed(1)}`;
}
```

### 6.5 策略跟踪页面

修改：

- `frontend/src/features/strategy-tracking/StrategyTrackingPage.tsx`
- `frontend/src/features/strategy-tracking/StrategyTrackingFilters.tsx`
- `frontend/src/features/strategy-tracking/StrategyTrackingTable.tsx`
- `frontend/src/stores/strategyTrackingStore.ts`
- `frontend/src/api/client.ts`

新增筛选：

```text
全部 | 原低吸 | 前排加权 | 前排极精选
```

查询参数：

```text
strategy_variant=baseline
strategy_variant=front_row_weighted
strategy_variant=front_row_only
```

表格新增列：

```text
策略线
```

展示示例：

```text
前排加权
Paper验证
未接生产
```

`front_row_only` 展示：

```text
前排极精选
仅观察
不参与生产排序
```

### 6.6 策略跟踪后端

修改：

- `backend/app/models/schema_defs/strategy_tracking.py`
- `backend/app/services/strategy_tracking_builders.py`
- `backend/app/services/strategy_tracking_filters.py`
- `backend/app/services/strategy_tracking_snapshot.py`
- `backend/app/api/routes/strategy_tracking.py`

新增字段：

```python
strategy_variant: str = "baseline"
strategy_role: str = "production_baseline"
display_lane: str = "baseline"
display_lane_title: str = "原低吸策略"
production_sort_replaced: bool = False
paper_enabled: bool = False
watch_only: bool = False
matched_strategy_variants: list[str] = Field(default_factory=list)
```

新增过滤逻辑：

```python
if strategy_variant:
    items = [item for item in items if item.strategy_variant == strategy_variant]
```

---

## 7. Readiness 展示

从报告中提炼状态，可先由后端硬编码读取最新 JSON 报告，后续再持久化。

优先读取：

- `docs/reports/front-row-weighted-production-readiness-2026-05-30.json`
- `docs/reports/front-row-weighted-walk-forward-validation-2026-05-30.json`
- `docs/reports/front-row-weighted-minute-tick-tradability-2026-05-30.json`
- `docs/reports/front-row-weighted-weak-market-compression-2026-05-30.json`

`front_row_weighted` readiness 示例：

```json
{
  "status": "shadow_paper_extend_oos",
  "recommend_small_traffic_observation": false,
  "blockers": [
    "oos_window_below_60_trade_days",
    "walk_forward_pass_rate_below_70pct",
    "minute_coverage_below_95pct",
    "tick_data_insufficient_for_real_money_production"
  ]
}
```

前端展示为：

```text
小流量观察：否
阻断原因：
1. 样本外验证还不够 60 个交易日
2. 滚动验证表现不稳定
3. 分钟行情覆盖不足
4. 逐笔成交数据不足
```

`front_row_only` readiness 固定：

```json
{
  "status": "elite_watch_only",
  "recommend_small_traffic_observation": false,
  "blockers": [
    "front_row_only_not_production_filter",
    "low_frequency_long_no_signal_risk"
  ]
}
```

前端展示为：

```text
前排极精选只做提醒，不作为生产硬过滤。
原因：信号很少，历史上可能连续较长时间没有票。
```

---

## 8. 测试计划

### 8.1 后端单元测试

新增或更新：

- `backend/tests/test_low_buy_strategy_lanes.py`
- `backend/tests/test_low_buy_priority_board_strategy_variants.py`
- `backend/tests/test_strategy_tracking_strategy_variant_filters.py`

必须覆盖：

1. `front_row_only` 返回 `production_score is None`。
2. `front_row_only` 返回 `watch_only is True`。
3. `front_row_weighted` 返回 `paper_enabled is True` 且 `production_sort_replaced is False`。
4. `baseline` 排序仍使用旧 `priority_score`。
5. `front_row_weighted` 排序使用 `production_score`，但不影响 baseline。
6. 旧参数 `front_row_only=true` 等价于 `strategy_variant=front_row_only`。
7. 策略跟踪支持 `strategy_variant` 过滤。
8. 同票多策略命中时输出 `matched_strategy_variants`。

示例断言：

```python
def test_front_row_only_is_watch_only_without_production_score():
    item = build_lane_item(strategy_variant="front_row_only", watch_score=91.0)
    assert item.display_lane == "front_row_only"
    assert item.watch_only is True
    assert item.production_enabled is False
    assert item.production_score is None
```

### 8.2 前端测试

新增或更新：

- `frontend/src/features/low-buy/StrategyLaneTabs.test.tsx`
- `frontend/src/features/monitor/MonitorPage.test.tsx`
- `frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx`
- `frontend/src/mobile/MobileTabSections.test.tsx`

必须覆盖：

1. 页面出现三个策略入口：原低吸策略、前排加权、前排极精选。
2. 切到 `front_row_weighted` 后请求带 `strategy_variant=front_row_weighted`。
3. 切到 `front_row_only` 后请求带 `strategy_variant=front_row_only`。
4. `front_row_weighted` 显示 “Shadow/Paper 验证中”。
5. `front_row_only` 显示 “不参与生产排序”。
6. 策略跟踪可以按策略线筛选。
7. 同票命中多策略时显示“同时命中”标签。

示例：

```tsx
it("shows strategy lane tabs", () => {
  render(<StrategyLaneTabs value="baseline" onChange={vi.fn()} />);
  expect(screen.getByText("原低吸策略")).toBeInTheDocument();
  expect(screen.getByText("前排加权")).toBeInTheDocument();
  expect(screen.getByText("前排极精选")).toBeInTheDocument();
});
```

---

## 9. 执行步骤

### Task 1: 后端 lane 元数据

**Files:**

- Create: `backend/app/services/low_buy/strategy_lanes.py`
- Test: `backend/tests/test_low_buy_strategy_lanes.py`

- [ ] 新增 `StrategyLaneDefinition`、`LANES`、`resolve_strategy_lane()`。
- [ ] 测试三条 lane 的 role、title、production/paper/watch-only 状态。
- [ ] 运行：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_strategy_lanes.py
```

### Task 2: 后端 schema 扩展

**Files:**

- Modify: `backend/app/models/schema_defs/screener_parts/candidate.py`
- Modify: `backend/app/models/schema_defs/screener_parts/priority.py`

- [ ] 在 candidate 和 priority item 加 lane 字段。
- [ ] 在 priority response 加 `available_lanes / lane_summary / readiness_summary`。
- [ ] 确保默认值保持向后兼容。

### Task 3: Priority Board 变体 API

**Files:**

- Modify: `backend/app/api/routes/screeners.py`
- Modify: `backend/app/services/low_buy_screener.py`
- Modify: `backend/app/services/low_buy/priority_board.py`
- Modify: `backend/app/services/low_buy/priority_items.py`
- Test: `backend/tests/test_low_buy_priority_board_strategy_variants.py`

- [ ] 新增 `strategy_variant` query 参数。
- [ ] 保留 `front_row_only=true` 兼容逻辑。
- [ ] `baseline` 使用旧排序。
- [ ] `front_row_weighted` 使用前排加权 Shadow/Paper 排序。
- [ ] `front_row_only` 使用观察分排序，且 `production_score=None`。
- [ ] 输出 `matched_strategy_variants`。
- [ ] 运行相关测试。

### Task 4: 策略跟踪支持 strategy_variant

**Files:**

- Modify: `backend/app/models/schema_defs/strategy_tracking.py`
- Modify: `backend/app/services/strategy_tracking_builders.py`
- Modify: `backend/app/services/strategy_tracking_filters.py`
- Modify: `backend/app/services/strategy_tracking_snapshot.py`
- Modify: `backend/app/api/routes/strategy_tracking.py`
- Test: `backend/tests/test_strategy_tracking_strategy_variant_filters.py`

- [ ] 给跟踪 item 加 lane 字段。
- [ ] 快照 payload 保留 lane 字段。
- [ ] 列表接口支持 `strategy_variant` 过滤。
- [ ] 策略表现按 lane 可单独统计。

### Task 5: 前端类型与 API

**Files:**

- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/appClient.ts`

- [ ] 增加 `StrategyVariant / StrategyRole / DisplayLane / StrategyLaneMeta` 类型。
- [ ] 低吸 priority board 请求增加 `strategy_variant`。
- [ ] 策略跟踪 query 增加 `strategy_variant`。

### Task 6: 低吸榜三策略视图

**Files:**

- Create: `frontend/src/features/low-buy/StrategyLaneTabs.tsx`
- Create: `frontend/src/features/low-buy/StrategyLaneStatusCard.tsx`
- Create: `frontend/src/features/low-buy/StrategyLaneCandidateCard.tsx`
- Modify: `frontend/src/features/monitor/MonitorPage.tsx`
- Modify: `frontend/src/mobile/MobileTabSections.tsx`
- Modify: `frontend/src/mobile/MobileDesignCards.tsx`
- Test: `frontend/src/features/low-buy/StrategyLaneTabs.test.tsx`
- Test: `frontend/src/features/monitor/MonitorPage.test.tsx`

- [ ] 增加三段式策略切换。
- [ ] 切换时刷新对应 lane 数据。
- [ ] 展示 lane 状态卡。
- [ ] 卡片显示 Shadow/Paper、仅观察、不参与生产排序等状态。
- [ ] 避免同一 lane 内重复股票。

### Task 7: 策略跟踪前端筛选与表格列

**Files:**

- Modify: `frontend/src/features/strategy-tracking/StrategyTrackingPage.tsx`
- Modify: `frontend/src/features/strategy-tracking/StrategyTrackingFilters.tsx`
- Modify: `frontend/src/features/strategy-tracking/StrategyTrackingTable.tsx`
- Modify: `frontend/src/stores/strategyTrackingStore.ts`
- Test: `frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx`

- [ ] 增加“全部 / 原低吸 / 前排加权 / 前排极精选”筛选。
- [ ] 请求参数带 `strategy_variant`。
- [ ] 表格增加“策略线”列。
- [ ] 明确显示 `Paper验证`、`仅观察`、`未接生产`。

### Task 8: Readiness 状态接入

**Files:**

- Create: `backend/app/services/low_buy/front_row_readiness.py`
- Modify: `backend/app/services/low_buy/priority_board.py`
- Modify: `frontend/src/features/low-buy/StrategyLaneStatusCard.tsx`
- Test: `backend/tests/test_front_row_readiness.py`

- [ ] 读取最新 readiness JSON 报告。
- [ ] 输出 `readiness_summary`。
- [ ] 前端把 blocker 转成中文短文案。
- [ ] 若报告不存在，显示 `readiness_unknown`，不得默认通过。

### Task 9: 回归测试

运行：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_strategy_lanes.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_strategy_tracking_strategy_variant_filters.py \
  backend/tests/test_low_buy_production_scoring.py \
  backend/tests/test_front_row_weighted_readiness.py
```

运行前端：

```bash
npm --prefix frontend test -- --run \
  frontend/src/features/low-buy/StrategyLaneTabs.test.tsx \
  frontend/src/features/monitor/MonitorPage.test.tsx \
  frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx
```

如果本地前端测试框架不支持按文件筛选，改用项目现有测试命令，但必须至少覆盖上述组件。

---

## 10. 验收标准

### 功能验收

1. 低吸优先榜能看到三个入口：原低吸策略、前排加权、前排极精选。
2. `baseline` 页面排序和旧版本一致。
3. `front_row_weighted` 页面显示 Shadow/Paper 状态，且不显示为已生产。
4. `front_row_only` 页面显示仅观察，不参与生产排序。
5. 策略跟踪可按三条策略线筛选。
6. 同票多策略命中时显示“同时命中”标签。
7. `front_row_only` 任意返回项 `production_score` 为 `null`。
8. `front_row_weighted` 任意返回项 `production_sort_replaced` 为 `false`。
9. 页面展示 OOS、walk-forward、分钟/逐笔、弱市压缩等 readiness 阻断状态。

### 风险验收

1. 没有改动旧生产排序默认逻辑。
2. 没有把 `front_row_only` 作为生产硬过滤。
3. 没有把 `near_entry` 放进生产收益排行。
4. 没有把每日信号等权复利当真实组合收益展示。
5. 没有新增部署动作。

### 测试验收

1. 后端 lane 和 priority board 相关测试通过。
2. 策略跟踪过滤测试通过。
3. 前端三策略入口测试通过。
4. 现有低吸生产评分测试仍通过。

---

## 11. 推荐上线节奏

本计划完成后仍不建议直接实盘或替换生产排序。推荐节奏：

1. 先只在开发环境和本地报告页面展示。
2. 再进入线上只读展示，但保持默认 tab 为旧策略。
3. `front_row_weighted` 累积 Shadow/Paper 样本。
4. OOS 满 60 个交易日、walk-forward 达标、分钟/逐笔可成交性达标后，再评估是否小流量观察。
5. `front_row_only` 永久保持极精选雷达定位，除非后续有新的充分验证推翻低频风险。

---

## 12. 最终产品形态

用户打开低吸页面时应该看到：

```text
原低吸策略
当前生产观察基准，保持旧排序。

前排加权
前排加权、后排降权、极端后排剔除。
Shadow/Paper 验证中，未替换生产排序。

前排极精选
只显示强前排票。
仅观察提醒，不作为生产硬过滤。
```

用户打开策略跟踪时应该能按策略线查看：

```text
全部 | 原低吸 | 前排加权 | 前排极精选
```

并且每条记录都能明确说明：

```text
来源策略：前排加权
角色：Paper验证
生产状态：未接生产
```

或：

```text
来源策略：前排极精选
角色：强前排观察
生产状态：不参与生产排序
```

这样三条策略各司其职：旧策略负责稳定基准，`front_row_weighted` 负责未来候选验证，`front_row_only` 负责极精选提醒。
