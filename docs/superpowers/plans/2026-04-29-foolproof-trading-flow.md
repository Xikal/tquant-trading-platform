# Foolproof Trading Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前专业交易平台收敛成“今天能不能做、买哪只、多少钱买、错了怎么走、最多拿几天”的傻瓜式 App 使用流程，同时保留 Web 专业能力不受影响。

**Architecture:** 后端新增轻量决策层，把市场环境、优先级榜、策略生产层、推荐天数、持仓信号统一翻译成普通用户可执行语言。前端 App 使用新决策字段重排首页和榜单，Web 原有页面尽量只消费兼容字段，不强制重构。AI 只解释硬规则结果，不参与放宽策略。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, React, Capacitor, TypeScript, Android Gradle.

---

## Scope And Non-Goals

**本轮必须完成：**

- 修复已知 review 问题：内存缓存命中归一化、推荐天数文案重复。
- App 首页新增“今日交易灯”：`可交易 / 只观察 / 空仓等待`。
- 全策略榜在 App 端改为三类：`确定可买 / 等到价格 / 放弃观察`。
- 每只票展示：买点区、止损位、建议仓位、推荐天数、下一步动作。
- 做T文案改成普通用户动作：`现在能买回 / 现在能卖一部分 / 今天别动`。
- 市场环境术语翻译为：`适合出手 / 只做龙头 / 别追高 / 先别买`。
- AI 解读改固定模板弹窗：`能不能买 / 为什么 / 最大风险 / 明天怎么处理`。
- App 构建、Android APK、云端部署、更新清单版本递增。

**本轮不做：**

- 不新增复杂会员权限。
- 不重写全部策略公式。
- 不让 AI 参与买点放宽或策略评分。
- 不强制改 Web 桌面端所有布局，只保持兼容和关键字段可用。

---

## File Map

### Backend

- Modify: `backend/app/services/low_buy/results.py`
  - 缓存命中也必须走策略归一化和推荐天数补挂。
- Modify: `backend/app/services/low_buy/priority_board.py`
  - 去掉重复推荐天数文案，输出统一“第 N 天 / 剩余 X 天验证窗口”。
- Create: `backend/app/services/low_buy/simple_decision.py`
  - 纯函数：生成今日交易灯、市场普通话术、优先级三类分组、下一步动作。
- Modify: `backend/app/models/schema_defs/screener.py`
  - 新增 `LowBuyDailyDecisionOut`、`LowBuySimpleBucketOut`、`simple_buckets`、`daily_decision` 字段。
- Modify: `backend/app/services/low_buy/priority_board.py`
  - 在 `LowBuyPriorityBoardResponse` 构造阶段挂 `daily_decision` 和 `simple_buckets`。
- Modify: `backend/app/models/schema_defs/app_mobile.py`
  - App 聚合模型补充普通话术字段，保持向后兼容。
- Modify: `backend/app/services/app_mobile/home.py`
  - 持仓卡片补充“今天动作”汇总字段，优先处理持仓。
- Modify: `backend/app/services/app_mobile/watchlist.py`
  - 做T信号文案翻译，不改原始 `signal` 结构。
- Modify: `backend/app/services/ai_decision_support.py` or existing AI support service file
  - AI 输出固定模板；如果模型异常，返回固定量化降级模板。
- Test: `backend/tests/test_low_buy_simple_decision.py`
  - 覆盖交易灯、三类分组、市场话术、推荐天数窗口。
- Test: `backend/tests/test_app_mobile_service.py`
  - 覆盖 App 首页持仓动作和普通文案。
- Test: `backend/tests/test_ai_decision_support.py`
  - 覆盖固定模板和降级输出。

### Frontend

- Create: `frontend/src/mobile/simpleDecision.ts`
  - 前端兜底派生：当后端旧版本缺字段时仍能显示三类榜单。
- Create: `frontend/src/mobile/plainTradingText.ts`
  - 统一翻译市场环境、做T动作、信号状态。
- Modify: `frontend/src/types/playbook.ts`
  - 新增后端 simple decision 类型。
- Modify: `frontend/src/types/app.ts`
  - 新增 App 首页今日结论和持仓动作字段。
- Modify: `frontend/src/features/app-preview/hooks.ts`
  - 加载并暴露 `dailyDecision`、`simpleBuckets`、`holdingActions`。
- Modify: `frontend/src/mobile/MobileApp.tsx`
  - 首页重排成四块：今日结论、可买榜、持仓处理、风险提醒。
- Modify: `frontend/src/features/app-preview/portfolio.tsx`
  - 榜单卡片固定显示：买点、止损、仓位、推荐天数、下一步。
- Modify: `frontend/src/mobile/mobileSections.tsx`
  - 详情弹窗强化退出计划和推荐天数，隐藏专业噪音。
- Modify: `frontend/src/styles/mobile/native-app.css`
  - 添加交易灯、三类榜单、AI 弹窗样式。
- Modify: `frontend/src/api/appClient.ts`
  - 如需要新增 AI 解读入口或固定模板弹窗 API 调用。
- Build validation:
  - `cd frontend && npm run build`
  - `cd frontend && npm run build:native`
  - `cd frontend && npm run cap:sync`
  - `cd frontend/android && ./gradlew assembleRelease`

### Docs And Release

- Modify: `APP_API_SPEC.md`
  - 补充 App 首页傻瓜式字段和更新接口说明。
- Modify: `frontend/android/app/build.gradle`
  - 发布时递增 `versionCode` 和 `versionName`。
- Publish:
  - 上传 APK 到 `/app/backend/data/app_updates/weis-quant-latest.apk`
  - 更新 `/app/backend/data/app_updates/android.json`

---

## Backend Decision Rules

### Daily Trading Lamp

`daily_decision.key` 取值：

- `tradable`: 可交易
- `observe_only`: 只观察
- `wait`: 空仓等待

规则：

```python
BLOCKED_MARKETS = {"risk_release", "high_flyer_retreat"}
CAUTIOUS_MARKETS = {"fast_rotation", "weight_support", "low_volume_wait"}
GOOD_MARKETS = {"broad_rally", "repair", "neutral"}

def decide_daily_action(board) -> str:
    if board.market_state in BLOCKED_MARKETS:
        return "wait"
    if board.immediate_count > 0 and board.market_state in GOOD_MARKETS:
        return "tradable"
    if board.focus_count > 0 or board.track_count > 0:
        return "observe_only"
    if board.market_state in CAUTIOUS_MARKETS:
        return "observe_only"
    return "wait"
```

普通话术：

- `tradable`: `今天可以小仓试错，只看确定可买里的前 1-3 只。`
- `observe_only`: `今天先等价格和承接，不追高，不提前买。`
- `wait`: `今天不适合新开仓，优先处理持仓或空仓等待。`

### Market Plain Text

映射：

- `broad_rally`: `适合出手`
- `repair`: `适合小仓试错`
- `fast_rotation`: `轮动太快，只做最强主线`
- `weight_support`: `指数被权重托住，题材股别追高`
- `high_flyer_retreat`: `高位退潮，先别买`
- `risk_release`: `风险释放中，空仓等待`
- `low_volume_wait`: `缩量观望，等放量确认`
- `neutral`: `环境一般，小仓观察`

### Simple Buckets

分组规则：

- `确定可买`: `buy_signal_state in {"buy_now", "soft_buy_now"}` 且策略层允许生产执行。
- `等到价格`: `buy_signal_state == "near_entry"` 或价格未进入买点区但结构仍有效。
- `放弃观察`: `buy_signal_state in {"watch", "avoid"}`、策略为研究层、已超过推荐窗口、市场硬阻断。

每组最多显示：

- App 首页：每组最多 3 只。
- App 榜单页：每组最多 10 只。

### Recommendation Window

显示文案统一：

```text
{策略名}第 {N} 天，建议验证窗口 {max_days} 天；剩余 {remaining} 天。
```

如果超过窗口：

```text
已超过建议验证窗口，未转强应降级或取消关注。
```

默认窗口：

- 生产策略：3 个交易日。
- 观察策略：2 个交易日。
- 研究策略：不显示仓位，只显示研究原因。

### Holding Action Text

做T/持仓动作映射：

- `positive_t`: `现在能买回`
- `negative_t`: `现在能卖一部分`
- `hold`: `今天别动`
- `stop_loss`: `触发止损，先退出`

持仓卡片必须显示：

```text
动作：今天别动
原因：价格未到触发位
失效：跌破 10.20 需要处理
```

---

## Tasks

### Task 1: Fix Existing Review Findings

**Files:**

- Modify: `backend/app/services/low_buy/results.py`
- Modify: `backend/app/services/low_buy/priority_board.py`
- Test: `backend/tests/test_low_buy_read_paths.py`
- Test: `backend/tests/test_low_buy_recommendation_duration.py`

- [ ] Step 1: Add or update a test that simulates cached full result read.

Test expectation:

```python
def test_cached_full_result_still_normalizes_policy_and_duration(self):
    # Build a cached response with paused strategy buy_now.
    # Read it again through the public read path.
    # Assert signal is downgraded and recommendation text exists.
    self.assertEqual(candidate.buy_signal_state, "near_entry")
    self.assertTrue(candidate.recommendation_duration_text)
```

- [ ] Step 2: Modify cache hit branch in `results.py`.

Implementation intent:

```python
if cached_full is not None:
    normalized = self._normalize_response_candidate_policy_state(cached_full)
    return self._attach_recommendation_duration_to_response(db, normalized)
```

- [ ] Step 3: Add or update a test for priority board recommendation text.

Expected:

```python
self.assertNotIn("连续推荐：", item.action_summary)
self.assertEqual(item.recommendation_duration_text.count("推荐"), 1)
```

- [ ] Step 4: Modify `priority_board.py` text composition.

Implementation intent:

```python
duration_text = build_priority_duration_text(candidate)
item.recommendation_duration_text = duration_text
item.action_summary = append_once(item.action_summary, duration_text)
```

- [ ] Step 5: Run tests.

Command:

```bash
PYTHONPATH=/Users/j/Documents/gupiao/backend backend/.venv/bin/python -m unittest \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_low_buy_recommendation_duration.py \
  backend/tests/test_priority_weighting.py
```

Expected: `OK`

---

### Task 2: Backend Simple Decision Layer

**Files:**

- Create: `backend/app/services/low_buy/simple_decision.py`
- Modify: `backend/app/models/schema_defs/screener.py`
- Modify: `backend/app/services/low_buy/priority_board.py`
- Test: `backend/tests/test_low_buy_simple_decision.py`

- [ ] Step 1: Create schema models.

Add to `screener.py`:

```python
class LowBuyDailyDecisionOut(BaseModel):
    key: Literal["tradable", "observe_only", "wait"] = "wait"
    title: str = "空仓等待"
    message: str = "今天不适合新开仓。"
    market_plain_text: str = ""
    risk_level: Literal["low", "medium", "high"] = "medium"
    action_steps: list[str] = Field(default_factory=list)


class LowBuySimpleBucketOut(BaseModel):
    key: Literal["buy_now", "wait_price", "give_up"] = "give_up"
    title: str
    description: str = ""
    count: int = 0
    symbols: list[str] = Field(default_factory=list)
```

Add optional fields to `LowBuyPriorityBoardResponse`:

```python
daily_decision: LowBuyDailyDecisionOut = Field(default_factory=LowBuyDailyDecisionOut)
simple_buckets: list[LowBuySimpleBucketOut] = Field(default_factory=list)
```

- [ ] Step 2: Implement pure functions in `simple_decision.py`.

Functions:

```python
def market_plain_text(market_state: str) -> str: ...
def build_daily_decision(board_payload) -> LowBuyDailyDecisionOut: ...
def build_simple_buckets(items: list[LowBuyPriorityBoardItemOut]) -> list[LowBuySimpleBucketOut]: ...
def next_action_text(item: LowBuyPriorityBoardItemOut) -> str: ...
```

- [ ] Step 3: Attach fields in `priority_board.py`.

At response construction:

```python
response.daily_decision = build_daily_decision(response)
response.simple_buckets = build_simple_buckets(response.items)
```

- [ ] Step 4: Write tests for market state and buckets.

Test cases:

```python
def test_weight_support_maps_to_observe_only(self):
    decision = build_daily_decision(fake_board(market_state="weight_support", immediate_count=0))
    self.assertEqual(decision.key, "observe_only")
    self.assertIn("别追高", decision.market_plain_text)

def test_buy_now_and_near_entry_bucketed_separately(self):
    buckets = build_simple_buckets([buy_now_item(), near_entry_item(), watch_item()])
    self.assertEqual(buckets[0].title, "确定可买")
    self.assertEqual(buckets[1].title, "等到价格")
    self.assertEqual(buckets[2].title, "放弃观察")
```

- [ ] Step 5: Run tests.

Command:

```bash
PYTHONPATH=/Users/j/Documents/gupiao/backend backend/.venv/bin/python -m unittest backend/tests/test_low_buy_simple_decision.py backend/tests/test_priority_weighting.py
```

Expected: `OK`

---

### Task 3: App Home Four-Block Dashboard

**Files:**

- Create: `frontend/src/mobile/simpleDecision.ts`
- Create: `frontend/src/mobile/plainTradingText.ts`
- Modify: `frontend/src/features/app-preview/hooks.ts`
- Modify: `frontend/src/mobile/MobileApp.tsx`
- Modify: `frontend/src/styles/mobile/native-app.css`

- [ ] Step 1: Add frontend fallback derivation.

`simpleDecision.ts` exports:

```ts
export function deriveDailyDecision(board: LowBuyPriorityBoardResult | null): DailyDecisionView
export function deriveSimpleBuckets(items: LowBuyPriorityBoardItem[]): SimpleBucketView[]
export function recommendationWindowText(item: LowBuyPriorityBoardItem): string
```

- [ ] Step 2: Add plain text mapping.

`plainTradingText.ts` exports:

```ts
export function plainMarketText(marketState: string): string
export function plainHoldingAction(action: string): string
export function plainRiskText(riskLevel: string): string
```

- [ ] Step 3: Update hook return values.

`useAppPreviewData` should expose:

```ts
dailyDecision
simpleBuckets
holdingActions
```

These should use backend fields when present and fallback functions when absent.

- [ ] Step 4: Replace App home content with four blocks.

`MobileApp.tsx` home mode layout:

```tsx
<DailyDecisionCard decision={dailyDecision} />
<SimpleBuyList bucket={simpleBuckets.buyNow} />
<HoldingActionList rows={holdingRows} />
<RiskReminderCard decision={dailyDecision} board={priorityBoard} />
```

- [ ] Step 5: Keep original watchlist and holdings accessible.

Use existing tabs:

```tsx
SegmentTabs: 今日操作 / 监控列表 / 持仓股
```

Default tab: `今日操作`.

- [ ] Step 6: Run native build.

Command:

```bash
cd /Users/j/Documents/gupiao/frontend && npm run build:native
```

Expected: build succeeds.

---

### Task 4: App Priority Board Three Buckets

**Files:**

- Modify: `frontend/src/features/app-preview/portfolio.tsx`
- Modify: `frontend/src/mobile/MobileApp.tsx`
- Modify: `frontend/src/styles/mobile/native-holdings.css`

- [ ] Step 1: Update priority card fixed fields.

Every card shows:

```text
股票名 / 代码
板块 / 主线状态
状态：确定可买 / 等到价格 / 放弃观察
买点：x-y
止损：z
仓位：n%
推荐：第 N 天
下一步：到价后小仓试 / 今天别追 / 取消关注
```

- [ ] Step 2: Render buckets instead of strategy group.

In low-buy tab:

```tsx
<SimpleBucketSection title="确定可买" items={buyNowItems} />
<SimpleBucketSection title="等到价格" items={waitPriceItems} />
<SimpleBucketSection title="放弃观察" items={giveUpItems} />
```

- [ ] Step 3: Empty states must be actionable.

Copy:

```text
当前没有确定可买。今天只观察，不提前买。
```

- [ ] Step 4: Verify not showing professional-only tags by default.

Hidden by default:

- raw score details
- strategy weight score
- market bonus
- attribution buckets

Available only inside detail sheet.

---

### Task 5: Holding And DoT Plain-Language Actions

**Files:**

- Modify: `backend/app/services/app_mobile/watchlist.py`
- Modify: `backend/app/models/schema_defs/app_mobile.py`
- Modify: `frontend/src/features/app-preview/portfolio.tsx`
- Modify: `frontend/src/mobile/plainTradingText.ts`
- Test: `backend/tests/test_app_mobile_service.py`

- [ ] Step 1: Add fields to `AppWatchlistCard`.

Fields:

```python
plain_action_text: str = ""
plain_action_reason: str = ""
plain_invalid_condition: str = ""
```

- [ ] Step 2: Fill fields from signal.

Rules:

```python
positive_t -> "现在能买回"
negative_t -> "现在能卖一部分"
hold -> "今天别动"
high risk -> "风险偏高，先别加仓"
```

- [ ] Step 3: Update holding card.

Display:

```tsx
<strong>{plain_action_text}</strong>
<small>{plain_action_reason}</small>
<small>{plain_invalid_condition}</small>
```

- [ ] Step 4: Add tests.

Expected:

```python
self.assertEqual(card.plain_action_text, "现在能买回")
self.assertIn("触发价", card.plain_action_reason)
```

---

### Task 6: Exit Plan And Recommendation Window Display

**Files:**

- Modify: `backend/app/services/low_buy/priority_board.py`
- Modify: `frontend/src/mobile/mobileSections.tsx`
- Modify: `frontend/src/features/app-preview/portfolio.tsx`
- Test: `backend/tests/test_low_buy_recommendation_duration.py`

- [ ] Step 1: Normalize recommendation text.

Use one sentence only:

```text
首板回调第 2 天，建议验证窗口 3 天；剩余 1 天。
```

- [ ] Step 2: Add next-day plan text.

For every actionable candidate:

```text
第1天：到买点区且止跌再试仓。
第2天：冲高3%-5%先减仓。
第3天：未转强则退出或取消关注。
```

- [ ] Step 3: Detail sheet shows exit plan above reasons.

Order:

1. 下一步动作
2. 买点/止损/仓位
3. 推荐第几天
4. 风险提示
5. 专业理由

---

### Task 7: AI Fixed Template Modal

**Files:**

- Modify: `backend/app/services/ai_decision_support.py` or current AI decision service
- Modify: `backend/app/api/routes/ai.py`
- Modify: `frontend/src/features/dashboard` AI components if used by Web
- Create or Modify: `frontend/src/mobile/AiDecisionSheet.tsx`
- Test: `backend/tests/test_ai_decision_support.py`

- [ ] Step 1: Backend fixed output shape.

Response should include or be parseable into:

```json
{
  "can_buy": "不能买 / 可以小仓 / 等到价格",
  "why": "一句话理由",
  "main_risk": "最大风险",
  "tomorrow_plan": "明天怎么处理"
}
```

- [ ] Step 2: AI prompt must forbid rule changes.

Prompt rule:

```text
你只能解释已通过量化硬规则的结果，不能放宽买点，不能新增买入建议。
```

- [ ] Step 3: Frontend modal.

Click “解读榜单”:

```tsx
<AiDecisionSheet open={aiOpen} fixedSections={...} />
```

If AI fails:

```text
AI 暂时不可用，已显示纯量化结论。今天按买点、止损和仓位执行即可。
```

---

### Task 8: App Update Version Bump And Release Flow

**Files:**

- Modify: `frontend/android/app/build.gradle`
- Modify: `frontend/.env.native.local`
- Modify: `frontend/.env.native.example`
- Publish: server `/app/backend/data/app_updates/android.json`

- [ ] Step 1: Increment version.

For next release:

```gradle
versionCode 3
versionName "1.0.2"
```

`.env.native.local`:

```env
VITE_NATIVE_VERSION_CODE=3
```

- [ ] Step 2: Build release APK.

Commands:

```bash
cd /Users/j/Documents/gupiao/frontend
npm run cap:sync
cd android
./gradlew assembleRelease
```

- [ ] Step 3: Publish update manifest.

`android.json`:

```json
{
  "latest_version_code": 3,
  "latest_version_name": "1.0.2",
  "min_supported_version_code": 1,
  "mandatory": false,
  "title": "发现新版本 1.0.2",
  "message": "新增傻瓜式今日操作面板和三类榜单。",
  "changelog": [
    "新增今日交易灯",
    "全策略榜改为确定可买/等到价格/放弃观察",
    "持仓做T动作改为普通话术"
  ],
  "published_at": "2026-04-29 20:00:00"
}
```

- [ ] Step 4: Verify update endpoint.

Command:

```bash
curl -sS 'http://43.143.243.97:18090/api/app/update/android?current_version_code=2' | python3 -m json.tool
```

Expected:

```json
"update_available": true
```

---

### Task 9: Regression And Deployment

**Files:**

- No new code files.
- Validate full touched surface.

- [ ] Step 1: Backend compile.

```bash
python3 -m compileall -q backend/app backend/tests
```

Expected: no output.

- [ ] Step 2: Backend tests.

```bash
PYTHONPATH=/Users/j/Documents/gupiao/backend backend/.venv/bin/python -m unittest \
  backend/tests/test_low_buy_simple_decision.py \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_low_buy_recommendation_duration.py \
  backend/tests/test_priority_weighting.py \
  backend/tests/test_app_mobile_service.py \
  backend/tests/test_app_mobile_routes.py \
  backend/tests/test_ai_decision_support.py
```

Expected: `OK`

- [ ] Step 3: Frontend builds.

```bash
cd /Users/j/Documents/gupiao/frontend
npm run build
npm run build:native
```

Expected: both pass. Existing chunk size warning is acceptable.

- [ ] Step 4: Android build.

```bash
cd /Users/j/Documents/gupiao/frontend/android
./gradlew assembleRelease
```

Expected: `BUILD SUCCESSFUL`

- [ ] Step 5: Deploy cloud.

Use existing deploy flow:

```bash
rsync -az --delete -e 'ssh -i /Users/j/Downloads/gupiao.pem -o StrictHostKeyChecking=no' \
  --exclude '.env' --exclude '.git' --exclude '.DS_Store' --exclude '.runtime' \
  --exclude 'artifacts' --exclude 'data' --exclude 'backend/.venv' --exclude 'backend/data' \
  --exclude 'frontend/node_modules' --exclude 'frontend/dist' --exclude 'frontend/dist-native' \
  --exclude 'frontend/android' --exclude 'frontend/ios' --exclude '*.tgz' \
  /Users/j/Documents/gupiao/ ubuntu@43.143.243.97:/opt/gupiao/
```

Then:

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 \
  "cd /opt/gupiao && echo 'bjl.199602' | sudo -S docker compose -f docker-compose.mysql.yml up -d --build app"
```

- [ ] Step 6: Smoke test.

Commands:

```bash
curl -sS http://43.143.243.97:18090/readyz
curl -sS 'http://43.143.243.97:18090/api/screeners/low-buy/priority-board?limit=3'
curl -sS 'http://43.143.243.97:18090/api/app/update/android?current_version_code=2'
```

Expected:

- `readyz.status == ok`
- priority board returns 200
- update endpoint returns JSON

---

## Acceptance Checklist

- [ ] 用户打开 App 首页，不需要理解策略名，也能看到今天是否能交易。
- [ ] App 首页首屏只有四类核心信息：今日结论、可买榜、持仓处理、风险提醒。
- [ ] 全策略榜 App 端不再按策略分组，改为确定可买、等到价格、放弃观察。
- [ ] 每只票都明确显示买点、止损、仓位、推荐第几天、下一步动作。
- [ ] 做T不再显示抽象术语为主，显示“现在能买回/现在能卖一部分/今天别动”。
- [ ] 市场环境状态全部有普通话术，不再只显示权重护盘、退潮、弱扩散等术语。
- [ ] AI 解读固定模板，不输出长文，不改变硬规则建议。
- [ ] Web 原有公共接口仍可用。
- [ ] App 登录、用户持仓隔离、App 更新器仍可用。
- [ ] Android APK 能安装，旧版能看到更新提示。

---

## Execution Recommendation

推荐分两轮实施：

**第一轮 P0：**

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 6

产出：App 已经变成傻瓜式主流程。

**第二轮 P1：**

1. Task 5
2. Task 7
3. Task 8
4. Task 9

产出：做T、AI、发布链路完整闭环。

---

## Risk Controls

- 所有新增后端字段必须有默认值，避免旧前端或旧缓存反序列化失败。
- 前端必须有 fallback 派生逻辑，避免云端尚未部署最新后端时 App 白屏。
- AI 失败必须降级到纯量化结论，不能阻塞榜单。
- 不允许把观察/研究策略重新放回强买榜。
- 不允许用 AI 输出覆盖后端买点、止损、仓位。
- App 更新器只提示安装，不能尝试静默安装。
