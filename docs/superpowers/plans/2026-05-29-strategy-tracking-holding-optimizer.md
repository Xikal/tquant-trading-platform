# Strategy Tracking Holding Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only strategy tracking layer that computes per-recommendation best holding windows, drawdown-aware exit points, and a short-term-to-midlong holding qualification without writing strategy scores, rankings, or trade ledgers.

**Architecture:** Keep `/strategy-tracking` as an observation and review workspace. Backend computes posterior holding outcomes only from bars after the first signal, and computes long-hold eligibility as a daily as-of-state using only bars available up to each evaluated date. Frontend exposes concise list badges and a detail panel so users can see whether profit came from short-term spikes, controlled trend extension, or unacceptable drawdown.

**Tech Stack:** FastAPI/Pydantic/SQLAlchemy backend, `DailyHistoryRepository` daily bars, existing Rust/Python finance math fallback, Go BFF read aggregation, React + TypeScript + Ant Design frontend, pytest/vitest/Go tests.

---

## Product Rules And Safety Boundaries

This feature must stay strictly read-only:

- It must not update `LowBuyResultSnapshot`, `LowBuyTradeLifecycleSnapshot`, paper trading ledgers, rankings, or strategy metadata.
- It must not produce automatic buy/sell orders.
- It may display recommendations such as `短线止盈`, `继续观察`, `可转中线`, `趋势破坏退出`, but these are review labels only.
- It must distinguish posterior review metrics from real-time decision metrics. `best_holding_days` and `best_exit_return_pct` are hindsight review metrics; `hold_extension_state` is computed day by day from visible history.
- It must avoid future functions: any long-hold decision for date `D` can only use bars with `trade_date <= D`; best-exit metrics are explicitly labeled as `posterior_review`.

## Functional Scope

For every tracked recommendation, add:

1. **Holding outcome statistics**
   - `best_holding_days`: number of trading days from first signal to the best drawdown-adjusted exit point.
   - `best_exit_date`: trade date of the best drawdown-adjusted exit.
   - `best_exit_return_pct`: return from first signal price to best exit close/high depending on policy.
   - `best_exit_drawdown_pct`: max drawdown endured up to that exit.
   - `return_drawdown_ratio`: reward-to-drawdown quality ratio.
   - `giveback_from_peak_pct`: how much profit was given back from post-signal peak to current/latest close.
   - `holding_bucket`: `short_1_3d`, `swing_4_10d`, `trend_11_30d`, `midlong_31_120d`, or `unavailable`.

2. **Drawdown-aware exit classification**
   - `exit_quality`: `excellent`, `acceptable`, `late_exit`, `drawdown_excessive`, `no_profit`, `unavailable`.
   - `exit_reason`: human readable reason, e.g. `3日内冲高，回撤受控`, `收益回吐超过阈值`, `最大回撤超过阈值`.

3. **Short-term to mid/long-term conversion qualification**
   - `hold_extension_state`: `not_qualified`, `watch`, `qualified`, `risk_off`, `unavailable`.
   - `hold_extension_text`: concise UI text.
   - `hold_extension_score`: 0-100, only for review ranking in the tracking page.
   - `hold_extension_reasons`: list of reasons.
   - `hold_extension_risks`: list of risks.
   - `suggested_holding_plan`: `short_take_profit`, `swing_hold`, `trend_hold`, `midlong_hold`, `exit_review`, `unavailable`.

## Suggested Default Thresholds

Keep thresholds centralized and conservative in a new backend constants file section:

- Short-term spike profit: `>= 5%` within 1-3 trading days.
- Swing continuation profit: `>= 8%` within 4-10 trading days.
- Mid/long qualification minimum profit cushion: `>= 8%` from first signal or `>= 5%` from entry zone high.
- Max tolerated drawdown for extension: no worse than `-6%` from close sequence or no breach of strategy stop loss.
- Profit giveback warning: peak-to-current giveback `>= 35%` of peak profit.
- Trend requirement for extension: latest close above MA20 and MA20 slope non-negative; for stronger midlong, close above MA60 when at least 60 bars are available.
- Volume/quality guard: latest 5-day average amount should not collapse below 60% of prior 20-day average amount when enough history exists.
- Data requirement: at least 10 post-signal trading bars for `trend_hold`; at least 30 post-signal bars for `midlong_hold`; otherwise state can only be `watch`.

These are first-pass review thresholds. Production eligibility should require later walk-forward validation by strategy family.

## File Structure

- Create `backend/app/services/strategy_tracking_holding.py`
  - Pure functions for holding outcome, drawdown-aware best exit, giveback, moving averages, and hold-extension classification.
  - No database access and no writes.

- Modify `backend/app/models/schema_defs/strategy_tracking.py`
  - Add holding outcome fields to `StrategyTrackingItemOut` and `StrategyTrackingTimelinePointOut`.
  - Keep defaults nullable or safe strings to avoid breaking old clients.

- Modify `backend/app/services/strategy_tracking_builders.py`
  - Call the new holding calculator from `build_tracking_item` and `build_timeline`.
  - Add markers for `best_exit` and `hold_extension`.

- Modify `backend/app/services/strategy_tracking_helpers.py`
  - Add aggregate fields if needed in `build_summary` and `build_performance`, or keep performance table unchanged for the first task to avoid scope creep.

- Modify `backend/app/services/strategy_tracking.py`
  - Fetch enough pre-signal bars for MA20/MA60 calculations. Current `_fetch_bars()` starts at first signal; this feature needs a pre-signal lookback. Add a helper that backs up by calendar days or fetches from a wider start date, then have builders split pre/post internally.

- Modify `backend/tests/test_strategy_tracking.py`
  - Add tests for best holding window, drawdown cap, no future function in extension state, and read-only refresh.

- Modify `frontend/src/types/strategyTracking.ts`
  - Add new fields matching Pydantic schema.

- Modify `frontend/src/features/strategy-tracking/strategyTrackingFormatters.ts`
  - Add display helpers for holding bucket, exit quality, extension state, and score tone.

- Modify `frontend/src/features/strategy-tracking/StrategyTrackingTable.tsx`
  - Add columns/badges for best holding days and hold-extension state.

- Modify `frontend/src/features/strategy-tracking/StrategyTrackingDetailDrawer.tsx`
  - Add a holding plan summary and timeline columns for best exit / extension eligibility.

- Modify `frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx`
  - Assert new labels render and old read-only behavior still renders.

- Modify `go-services/bff-gateway/cmd/bff-gateway/main_test.go` only if tests rely on exact fixture strings. The BFF passes JSON through, so no Go schema change should be needed.

---

### Task 1: Backend Holding Calculator

**Files:**
- Create: `backend/app/services/strategy_tracking_holding.py`
- Test: `backend/tests/test_strategy_tracking.py`

- [ ] **Step 1: Add failing backend tests for best holding window and drawdown-aware exit**

Append this test to `StrategyTrackingTests` in `backend/tests/test_strategy_tracking.py`:

```python
    def test_items_include_drawdown_aware_best_holding_window(self) -> None:
        self._seed_holding_optimizer_fixture()

        response = self.client.get("/api/strategy-tracking/items?range=20&limit=10")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        item = next(row for row in body["items"] if row["symbol"] == "600010")
        self.assertEqual(item["best_holding_days"], 4)
        self.assertEqual(item["best_exit_date"], "2026-04-24")
        self.assertGreaterEqual(item["best_exit_return_pct"], 11.0)
        self.assertGreater(item["return_drawdown_ratio"], 1.5)
        self.assertEqual(item["holding_bucket"], "swing_4_10d")
        self.assertIn(item["exit_quality"], {"excellent", "acceptable"})
        self.assertFalse(body["production_writeable"])
```

Add this helper fixture to the same class:

```python
    def _seed_holding_optimizer_fixture(self) -> None:
        with self.Session() as db:
            self._seed_metadata(db)
            db.add(
                LowBuyResultSnapshot(
                    latest_trade_date="2026-04-20",
                    strategy_key="first_board",
                    symbol="600010",
                    name="持有优化样本",
                    score=91,
                    buy_signal_state="buy_now",
                    payload_json=json.dumps(_payload(price=10.0), ensure_ascii=False),
                )
            )
            db.add_all(
                [
                    _bar("600010", "2026-04-01", high=9.3, low=8.9, close=9.1),
                    _bar("600010", "2026-04-02", high=9.4, low=9.0, close=9.2),
                    _bar("600010", "2026-04-03", high=9.5, low=9.1, close=9.3),
                    _bar("600010", "2026-04-06", high=9.6, low=9.2, close=9.4),
                    _bar("600010", "2026-04-07", high=9.7, low=9.3, close=9.5),
                    _bar("600010", "2026-04-08", high=9.8, low=9.4, close=9.6),
                    _bar("600010", "2026-04-09", high=9.9, low=9.5, close=9.7),
                    _bar("600010", "2026-04-10", high=10.0, low=9.6, close=9.8),
                    _bar("600010", "2026-04-13", high=10.1, low=9.7, close=9.9),
                    _bar("600010", "2026-04-14", high=10.2, low=9.8, close=10.0),
                    _bar("600010", "2026-04-15", high=10.2, low=9.8, close=10.0),
                    _bar("600010", "2026-04-16", high=10.3, low=9.9, close=10.1),
                    _bar("600010", "2026-04-17", high=10.3, low=9.9, close=10.1),
                    _bar("600010", "2026-04-20", high=10.2, low=9.8, close=10.0),
                    _bar("600010", "2026-04-21", high=10.6, low=9.9, close=10.4),
                    _bar("600010", "2026-04-22", high=10.9, low=10.2, close=10.7),
                    _bar("600010", "2026-04-23", high=11.1, low=10.5, close=10.9),
                    _bar("600010", "2026-04-24", high=11.4, low=10.7, close=11.2),
                    _bar("600010", "2026-04-27", high=11.0, low=10.1, close=10.2),
                    _bar("600010", "2026-04-28", high=10.5, low=9.4, close=9.7),
                ]
            )
            db.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_tracking.py::StrategyTrackingTests::test_items_include_drawdown_aware_best_holding_window -q
```

Expected: FAIL because fields such as `best_holding_days` do not exist.

- [ ] **Step 3: Create the holding calculator**

Create `backend/app/services/strategy_tracking_holding.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from app.repositories.low_buy import DailyBarRow
from app.services.finance.performance_math import sequence_max_drawdown_pct
from app.services.strategy_tracking_helpers import pct, round_or_none, round_value

SHORT_SPIKE_PROFIT_PCT = 5.0
SWING_CONTINUATION_PROFIT_PCT = 8.0
EXTENSION_MIN_PROFIT_CUSHION_PCT = 8.0
EXTENSION_MAX_DRAWDOWN_PCT = -6.0
GIVEBACK_WARN_RATIO = 0.35
TREND_MIN_BARS = 10
MIDLONG_MIN_BARS = 30


@dataclass(frozen=True)
class HoldingOutcome:
    best_holding_days: int = 0
    best_exit_date: str | None = None
    best_exit_return_pct: float | None = None
    best_exit_drawdown_pct: float | None = None
    return_drawdown_ratio: float | None = None
    giveback_from_peak_pct: float | None = None
    holding_bucket: str = "unavailable"
    exit_quality: str = "unavailable"
    exit_reason: str = "后续行情不足"
    hold_extension_state: str = "unavailable"
    hold_extension_text: str = "数据不足"
    hold_extension_score: int = 0
    hold_extension_reasons: list[str] = field(default_factory=list)
    hold_extension_risks: list[str] = field(default_factory=list)
    suggested_holding_plan: str = "unavailable"


def analyze_holding_outcome(
    *,
    bars: list[DailyBarRow],
    first_signal_date: str,
    reference_price: float | None,
    stop_loss: float | None,
) -> HoldingOutcome:
    if not reference_price or reference_price <= 0:
        return HoldingOutcome(exit_reason="推荐价缺失")
    ordered = sorted(bars, key=lambda item: item.trade_date)
    posterior = [bar for bar in ordered if bar.trade_date > first_signal_date]
    history_until_latest = [bar for bar in ordered if bar.trade_date <= (posterior[-1].trade_date if posterior else first_signal_date)]
    if not posterior:
        return HoldingOutcome(exit_reason="推荐日后行情不足")

    best_index = _best_exit_index(posterior, reference_price)
    best_bar = posterior[best_index]
    best_holding_days = best_index + 1
    closes_to_best = [reference_price] + [bar.close_price for bar in posterior[: best_index + 1]]
    best_exit_return = pct(best_bar.close_price, reference_price)
    best_exit_drawdown = sequence_max_drawdown_pct(closes_to_best)
    ratio = _return_drawdown_ratio(best_exit_return, best_exit_drawdown)
    peak_return = max(pct(bar.high_price, reference_price) for bar in posterior)
    current_return = pct(posterior[-1].close_price, reference_price)
    giveback = max(0.0, peak_return - current_return)
    extension = classify_hold_extension(
        history=history_until_latest,
        posterior=posterior,
        reference_price=reference_price,
        stop_loss=stop_loss,
        peak_return_pct=peak_return,
        current_return_pct=current_return,
    )
    return HoldingOutcome(
        best_holding_days=best_holding_days,
        best_exit_date=best_bar.trade_date,
        best_exit_return_pct=round_or_none(best_exit_return),
        best_exit_drawdown_pct=round_or_none(best_exit_drawdown),
        return_drawdown_ratio=round_or_none(ratio),
        giveback_from_peak_pct=round_or_none(giveback),
        holding_bucket=_holding_bucket(best_holding_days),
        exit_quality=_exit_quality(best_exit_return, best_exit_drawdown, giveback),
        exit_reason=_exit_reason(best_holding_days, best_exit_return, best_exit_drawdown, giveback),
        hold_extension_state=extension.hold_extension_state,
        hold_extension_text=extension.hold_extension_text,
        hold_extension_score=extension.hold_extension_score,
        hold_extension_reasons=extension.hold_extension_reasons,
        hold_extension_risks=extension.hold_extension_risks,
        suggested_holding_plan=extension.suggested_holding_plan,
    )


def classify_hold_extension(
    *,
    history: list[DailyBarRow],
    posterior: list[DailyBarRow],
    reference_price: float,
    stop_loss: float | None,
    peak_return_pct: float,
    current_return_pct: float,
) -> HoldingOutcome:
    if not posterior:
        return HoldingOutcome()
    latest = posterior[-1]
    closes = [bar.close_price for bar in history]
    amounts = [bar.amount for bar in history]
    drawdown = sequence_max_drawdown_pct([reference_price] + [bar.close_price for bar in posterior])
    reasons: list[str] = []
    risks: list[str] = []
    score = 0

    if current_return_pct >= EXTENSION_MIN_PROFIT_CUSHION_PCT:
        score += 25
        reasons.append("已有足够利润垫")
    else:
        risks.append("利润垫不足")

    if drawdown >= EXTENSION_MAX_DRAWDOWN_PCT:
        score += 20
        reasons.append("持有期回撤受控")
    else:
        risks.append("持有期回撤过大")

    ma20 = _moving_average(closes, 20)
    ma60 = _moving_average(closes, 60)
    ma20_prev = _moving_average(closes[:-5], 20) if len(closes) >= 25 else None
    if ma20 is not None and latest.close_price >= ma20 and (ma20_prev is None or ma20 >= ma20_prev):
        score += 25
        reasons.append("价格站上MA20且均线未走弱")
    else:
        risks.append("MA20趋势确认不足")

    if ma60 is not None and latest.close_price >= ma60:
        score += 15
        reasons.append("价格站上MA60")
    elif len(closes) >= 60:
        risks.append("未站上MA60")

    amount_ok = _amount_not_collapsing(amounts)
    if amount_ok is True:
        score += 15
        reasons.append("成交额未明显萎缩")
    elif amount_ok is False:
        risks.append("成交额明显萎缩")

    if stop_loss and latest.low_price <= stop_loss:
        return HoldingOutcome(
            hold_extension_state="risk_off",
            hold_extension_text="跌破止损，不适合延长持有",
            hold_extension_score=min(score, 30),
            hold_extension_reasons=reasons,
            hold_extension_risks=[*risks, "已触及止损"],
            suggested_holding_plan="exit_review",
        )

    giveback_ratio = ((peak_return_pct - current_return_pct) / peak_return_pct) if peak_return_pct > 0 else 0.0
    if giveback_ratio >= GIVEBACK_WARN_RATIO:
        risks.append("利润回吐过多")
        score = min(score, 55)

    if len(posterior) >= MIDLONG_MIN_BARS and score >= 80:
        return HoldingOutcome(
            hold_extension_state="qualified",
            hold_extension_text="可转中长线观察",
            hold_extension_score=score,
            hold_extension_reasons=reasons,
            hold_extension_risks=risks,
            suggested_holding_plan="midlong_hold",
        )
    if len(posterior) >= TREND_MIN_BARS and score >= 65:
        return HoldingOutcome(
            hold_extension_state="qualified",
            hold_extension_text="可转波段趋势持有",
            hold_extension_score=score,
            hold_extension_reasons=reasons,
            hold_extension_risks=risks,
            suggested_holding_plan="trend_hold",
        )
    if score >= 45:
        return HoldingOutcome(
            hold_extension_state="watch",
            hold_extension_text="继续观察，暂不确认中长线",
            hold_extension_score=score,
            hold_extension_reasons=reasons,
            hold_extension_risks=risks,
            suggested_holding_plan="swing_hold",
        )
    return HoldingOutcome(
        hold_extension_state="not_qualified",
        hold_extension_text="不适合延长持有",
        hold_extension_score=score,
        hold_extension_reasons=reasons,
        hold_extension_risks=risks,
        suggested_holding_plan="short_take_profit" if current_return_pct > 0 else "exit_review",
    )


def _best_exit_index(posterior: list[DailyBarRow], reference_price: float) -> int:
    best_score = -10_000.0
    best_index = 0
    closes: list[float] = [reference_price]
    for index, bar in enumerate(posterior):
        closes.append(bar.close_price)
        return_pct = pct(bar.close_price, reference_price)
        drawdown_pct = sequence_max_drawdown_pct(closes)
        penalty = abs(min(drawdown_pct, 0.0)) * 0.75
        giveback_penalty = max(0.0, max(pct(item.high_price, reference_price) for item in posterior[: index + 1]) - return_pct) * 0.35
        score = return_pct - penalty - giveback_penalty
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def _return_drawdown_ratio(return_pct: float, drawdown_pct: float) -> float:
    drawdown_abs = abs(min(drawdown_pct, 0.0))
    if drawdown_abs <= 0.01:
        return round_value(return_pct)
    return round_value(return_pct / drawdown_abs)


def _holding_bucket(days: int) -> str:
    if days <= 0:
        return "unavailable"
    if days <= 3:
        return "short_1_3d"
    if days <= 10:
        return "swing_4_10d"
    if days <= 30:
        return "trend_11_30d"
    return "midlong_31_120d"


def _exit_quality(return_pct: float, drawdown_pct: float, giveback_pct: float) -> str:
    if return_pct <= 0:
        return "no_profit"
    if drawdown_pct <= -10:
        return "drawdown_excessive"
    if giveback_pct >= max(4.0, return_pct * 0.5):
        return "late_exit"
    if return_pct >= 8 and drawdown_pct >= -6:
        return "excellent"
    return "acceptable"


def _exit_reason(days: int, return_pct: float, drawdown_pct: float, giveback_pct: float) -> str:
    if return_pct <= 0:
        return "推荐后未形成正收益窗口"
    if drawdown_pct <= -10:
        return "收益窗口伴随过大回撤"
    if giveback_pct >= max(4.0, return_pct * 0.5):
        return "最佳收益后回吐明显"
    if days <= 3:
        return "短线冲高窗口明确"
    if days <= 10:
        return "波段持有收益更优"
    if days <= 30:
        return "趋势持有收益更优"
    return "中长线持有收益更优"


def _moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _amount_not_collapsing(amounts: list[float]) -> bool | None:
    if len(amounts) < 25:
        return None
    recent = mean(amounts[-5:])
    baseline = mean(amounts[-25:-5])
    if baseline <= 0:
        return None
    return recent >= baseline * 0.6
```

- [ ] **Step 4: Run the focused calculator test again**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_tracking.py::StrategyTrackingTests::test_items_include_drawdown_aware_best_holding_window -q
```

Expected: still FAIL until schema and builder fields are wired.

---

### Task 2: Backend Schema And Builder Wiring

**Files:**
- Modify: `backend/app/models/schema_defs/strategy_tracking.py`
- Modify: `backend/app/services/strategy_tracking_builders.py`
- Modify: `backend/app/services/strategy_tracking.py`
- Test: `backend/tests/test_strategy_tracking.py`

- [ ] **Step 1: Add schema fields**

Add these fields to `StrategyTrackingItemOut` after `max_drawdown_pct`:

```python
    best_holding_days: int = 0
    best_exit_date: str | None = None
    best_exit_return_pct: float | None = None
    best_exit_drawdown_pct: float | None = None
    return_drawdown_ratio: float | None = None
    giveback_from_peak_pct: float | None = None
    holding_bucket: str = "unavailable"
    exit_quality: str = "unavailable"
    exit_reason: str = ""
    hold_extension_state: str = "unavailable"
    hold_extension_text: str = "数据不足"
    hold_extension_score: int = 0
    hold_extension_reasons: list[str] = Field(default_factory=list)
    hold_extension_risks: list[str] = Field(default_factory=list)
    suggested_holding_plan: str = "unavailable"
```

Add these fields to `StrategyTrackingTimelinePointOut` after `max_drawdown_pct`:

```python
    holding_day: int = 0
    is_best_exit: bool = False
    hold_extension_state: str = "unavailable"
```

- [ ] **Step 2: Wire calculator into item builder**

In `backend/app/services/strategy_tracking_builders.py`, import:

```python
from app.services.strategy_tracking_holding import analyze_holding_outcome
```

Inside `build_tracking_item`, after `stats = posterior_stats(...)`, add:

```python
    holding = analyze_holding_outcome(
        bars=bars,
        first_signal_date=first_signal_date,
        reference_price=first_price,
        stop_loss=stop_loss,
    )
```

Then set the new `StrategyTrackingItemOut` fields:

```python
        best_holding_days=holding.best_holding_days,
        best_exit_date=holding.best_exit_date,
        best_exit_return_pct=holding.best_exit_return_pct,
        best_exit_drawdown_pct=holding.best_exit_drawdown_pct,
        return_drawdown_ratio=holding.return_drawdown_ratio,
        giveback_from_peak_pct=holding.giveback_from_peak_pct,
        holding_bucket=holding.holding_bucket,
        exit_quality=holding.exit_quality,
        exit_reason=holding.exit_reason,
        hold_extension_state=holding.hold_extension_state,
        hold_extension_text=holding.hold_extension_text,
        hold_extension_score=holding.hold_extension_score,
        hold_extension_reasons=holding.hold_extension_reasons,
        hold_extension_risks=holding.hold_extension_risks,
        suggested_holding_plan=holding.suggested_holding_plan,
```

- [ ] **Step 3: Wire timeline best-exit marker fields**

In `build_timeline`, set `holding_day` and `is_best_exit`:

```python
        holding_day = len(timeline) + 1
```

Add to the timeline point:

```python
                holding_day=holding_day,
                is_best_exit=bool(item.best_exit_date and bar.trade_date == item.best_exit_date),
                hold_extension_state=item.hold_extension_state if bar.trade_date == item.latest_trade_date else "unavailable",
```

- [ ] **Step 4: Add chart markers**

In `build_markers`, after the highest marker block, add:

```python
    if item.best_exit_date:
        markers.append(
            StrategyTrackingMarkerOut(
                kind="best_exit",
                trade_date=item.best_exit_date,
                price=None,
                label=f"最优持有 {item.best_holding_days}天",
            )
        )
    if item.hold_extension_state in {"watch", "qualified"} and item.latest_trade_date:
        markers.append(
            StrategyTrackingMarkerOut(
                kind="hold_extension",
                trade_date=item.latest_trade_date,
                price=item.current_price,
                label=item.hold_extension_text,
            )
        )
```

- [ ] **Step 5: Fetch pre-signal history without future data**

In `backend/app/services/strategy_tracking.py`, import `date` and `timedelta`:

```python
from datetime import date, timedelta
```

Replace `_fetch_bars` start-date logic:

```python
        start_date = min(self._first_signal_date(item) for item in group_list)
```

with:

```python
        first_signal = min(self._first_signal_date(item) for item in group_list)
        start_date = _calendar_lookback(first_signal, 140)
```

Add this helper at the end of the file:

```python
def _calendar_lookback(trade_date: str, days: int) -> str:
    try:
        parsed = date.fromisoformat(trade_date)
    except ValueError:
        return trade_date
    return (parsed - timedelta(days=days)).isoformat()
```

This fetches pre-signal history for MA calculations. Posterior metrics must still filter `bar.trade_date > first_signal_date`, which the builder already does.

- [ ] **Step 6: Run backend tests**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_tracking.py -q
```

Expected: all strategy tracking tests pass.

---

### Task 3: No-Future-Function Test For Long-Hold Qualification

**Files:**
- Modify: `backend/tests/test_strategy_tracking.py`

- [ ] **Step 1: Add a regression test proving late bars do not qualify an early detail date**

Add this test:

```python
    def test_hold_extension_uses_as_of_visible_history_not_future_peak(self) -> None:
        self._seed_holding_optimizer_fixture()

        response = self.client.get("/api/strategy-tracking/items/first_board:600010:2026-04-20")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        timeline = body["timeline"]
        early = next(point for point in timeline if point["trade_date"] == "2026-04-21")
        latest = timeline[-1]
        self.assertFalse(early["is_best_exit"])
        self.assertEqual(early["hold_extension_state"], "unavailable")
        self.assertIn(latest["hold_extension_state"], {"unavailable", "watch", "qualified", "not_qualified", "risk_off"})
        self.assertEqual(body["item"]["best_exit_date"], "2026-04-24")
```

- [ ] **Step 2: Run the no-future test**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_tracking.py::StrategyTrackingTests::test_hold_extension_uses_as_of_visible_history_not_future_peak -q
```

Expected: PASS. The point of the test is that `best_exit_date` may be hindsight, but per-day extension state is not backfilled onto earlier dates.

---

### Task 4: Frontend Types And Formatters

**Files:**
- Modify: `frontend/src/types/strategyTracking.ts`
- Modify: `frontend/src/features/strategy-tracking/strategyTrackingFormatters.ts`
- Test: `frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx`

- [ ] **Step 1: Add TypeScript fields**

In `StrategyTrackingItem`, add after `max_drawdown_pct`:

```ts
  best_holding_days: number;
  best_exit_date: string | null;
  best_exit_return_pct: number | null;
  best_exit_drawdown_pct: number | null;
  return_drawdown_ratio: number | null;
  giveback_from_peak_pct: number | null;
  holding_bucket: string;
  exit_quality: string;
  exit_reason: string;
  hold_extension_state: string;
  hold_extension_text: string;
  hold_extension_score: number;
  hold_extension_reasons: string[];
  hold_extension_risks: string[];
  suggested_holding_plan: string;
```

In `StrategyTrackingTimelinePoint`, add after `max_drawdown_pct`:

```ts
  holding_day: number;
  is_best_exit: boolean;
  hold_extension_state: string;
```

- [ ] **Step 2: Add formatter helpers**

Append to `frontend/src/features/strategy-tracking/strategyTrackingFormatters.ts`:

```ts
export function holdingBucketText(value: string): string {
  const labels: Record<string, string> = {
    short_1_3d: "短线1-3天",
    swing_4_10d: "波段4-10天",
    trend_11_30d: "趋势11-30天",
    midlong_31_120d: "中长31-120天",
    unavailable: "暂无持有窗口",
  };
  return labels[value] || value || "暂无持有窗口";
}

export function exitQualityTone(value: string): "success" | "error" | "warning" | "default" {
  if (value === "excellent" || value === "acceptable") return "success";
  if (value === "drawdown_excessive" || value === "no_profit") return "error";
  if (value === "late_exit") return "warning";
  return "default";
}

export function holdExtensionTone(value: string): "success" | "error" | "warning" | "default" {
  if (value === "qualified") return "success";
  if (value === "risk_off" || value === "not_qualified") return "error";
  if (value === "watch") return "warning";
  return "default";
}

export function suggestedPlanText(value: string): string {
  const labels: Record<string, string> = {
    short_take_profit: "短线止盈",
    swing_hold: "波段持有",
    trend_hold: "趋势持有",
    midlong_hold: "中长线观察",
    exit_review: "退出复盘",
    unavailable: "暂无建议",
  };
  return labels[value] || value || "暂无建议";
}
```

- [ ] **Step 3: Update frontend test fixtures**

In `itemFixture()` inside `StrategyTrackingPage.test.tsx`, add values:

```ts
    best_holding_days: 4,
    best_exit_date: "2026-04-24",
    best_exit_return_pct: 12.0,
    best_exit_drawdown_pct: -2.1,
    return_drawdown_ratio: 5.71,
    giveback_from_peak_pct: 3.2,
    holding_bucket: "swing_4_10d",
    exit_quality: "excellent",
    exit_reason: "波段持有收益更优",
    hold_extension_state: "watch",
    hold_extension_text: "继续观察，暂不确认中长线",
    hold_extension_score: 55,
    hold_extension_reasons: ["已有足够利润垫"],
    hold_extension_risks: ["MA20趋势确认不足"],
    suggested_holding_plan: "swing_hold",
```

In each timeline fixture point, add:

```ts
      holding_day: 1,
      is_best_exit: false,
      hold_extension_state: "unavailable",
```

For the best-exit point, set `is_best_exit: true`.

- [ ] **Step 4: Run type-adjacent test to see UI failures before component changes**

Run:

```bash
cd frontend && npm test -- StrategyTrackingPage --run
```

Expected: tests compile, but no new labels are asserted yet.

---

### Task 5: Frontend List And Detail UI

**Files:**
- Modify: `frontend/src/features/strategy-tracking/StrategyTrackingTable.tsx`
- Modify: `frontend/src/features/strategy-tracking/StrategyTrackingDetailDrawer.tsx`
- Modify: `frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx`

- [ ] **Step 1: Add holding columns to the table**

Update imports in `StrategyTrackingTable.tsx`:

```ts
import { displayReturn, entryZoneText, exitQualityTone, holdingBucketText, holdExtensionTone, suggestedPlanText, trackingTone } from "./strategyTrackingFormatters";
```

Increase scroll width:

```tsx
      scroll={{ x: 1280 }}
```

Add this column after the existing `表现` column:

```tsx
    {
      title: "持有优化",
      width: 190,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <span>{item.best_holding_days ? `最优 ${item.best_holding_days}天` : "暂无持有窗口"}</span>
          <div className="strategy-tracking-tag-row">
            <Tag color={exitQualityTone(item.exit_quality)}>{displayReturn(item.best_exit_return_pct)}</Tag>
            <Tag>{holdingBucketText(item.holding_bucket)}</Tag>
          </div>
        </div>
      ),
    },
    {
      title: "延长持有",
      width: 180,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <Tag color={holdExtensionTone(item.hold_extension_state)}>{item.hold_extension_text}</Tag>
          <span>{suggestedPlanText(item.suggested_holding_plan)} · {item.hold_extension_score}分</span>
        </div>
      ),
    },
```

- [ ] **Step 2: Add detail summary block**

Update imports in `StrategyTrackingDetailDrawer.tsx`:

```ts
import { exitQualityTone, holdingBucketText, holdExtensionTone, suggestedPlanText } from "./strategyTrackingFormatters";
```

After the existing metric row, add:

```tsx
      <div className="strategy-tracking-detail-metrics">
        <span>最优持有 {item.best_holding_days || "--"}天</span>
        <span>最优退出 {item.best_exit_date || "--"}</span>
        <span>最优收益 {formatPct(item.best_exit_return_pct)}</span>
        <span>承受回撤 {formatPct(item.best_exit_drawdown_pct)}</span>
      </div>
      <div className="strategy-tracking-tag-row">
        <Tag color={exitQualityTone(item.exit_quality)}>{item.exit_reason || "暂无退出评价"}</Tag>
        <Tag>{holdingBucketText(item.holding_bucket)}</Tag>
        <Tag color={holdExtensionTone(item.hold_extension_state)}>{item.hold_extension_text}</Tag>
        <Tag>{suggestedPlanText(item.suggested_holding_plan)}</Tag>
      </div>
      {item.hold_extension_reasons.length || item.hold_extension_risks.length ? (
        <Alert
          type={item.hold_extension_state === "qualified" ? "success" : "info"}
          showIcon
          title={`延长持有评分 ${item.hold_extension_score}`}
          description={[...item.hold_extension_reasons, ...item.hold_extension_risks].join("；")}
        />
      ) : null}
```

- [ ] **Step 3: Add timeline columns**

In `timelineColumns`, add after the `日期` column:

```tsx
  { title: "持有", dataIndex: "holding_day", width: 70, render: (value) => value ? `${value}天` : "--" },
```

In the `标记` renderer, add:

```tsx
        {point.is_best_exit ? <Tag color="gold">最优退出</Tag> : null}
```

- [ ] **Step 4: Add UI assertions**

In `StrategyTrackingPage.test.tsx`, update `renders list rows...` expectations:

```ts
    expect(html).toContain("最优 4天");
    expect(html).toContain("波段4-10天");
    expect(html).toContain("继续观察");
```

Update `renders detail drawer...` expectations:

```ts
    expect(html).toContain("最优持有");
    expect(html).toContain("最优退出");
    expect(html).toContain("延长持有评分");
    expect(html).toContain("最优退出");
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend && npm test -- StrategyTrackingPage --run
```

Expected: PASS.

---

### Task 6: BFF And End-To-End Verification

**Files:**
- Modify only if required: `go-services/bff-gateway/cmd/bff-gateway/main_test.go`

- [ ] **Step 1: Run Go BFF tests**

Run:

```bash
go test ./go-services/bff-gateway/cmd/bff-gateway
```

Expected: PASS. The BFF aggregates JSON and should not need schema edits.

- [ ] **Step 2: Run backend strategy tracking tests**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_tracking.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend strategy tracking tests**

Run:

```bash
cd frontend && npm test -- StrategyTrackingPage --run
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend && npm run build:web
```

Expected: PASS. The strategy tracking bundle should not balloon materially; if it grows by more than about 15 KB gzip, inspect imports before committing.

- [ ] **Step 5: Manual API smoke**

Run local backend if needed, then call:

```bash
curl -s 'http://127.0.0.1:8000/api/strategy-tracking/items?range=60&limit=5' | jq '.items[] | {symbol,best_holding_days,best_exit_return_pct,holding_bucket,hold_extension_state,suggested_holding_plan,production_writeable:false}'
```

Expected: fields are present. `production_writeable` remains false at response level.

---

### Task 7: Documentation And Release Notes

**Files:**
- Modify: `docs/platform-slimming-and-strategy-tracking-development-plan-2026-05-29.md` or create a short addendum under `docs/reports/strategy-tracking-holding-optimizer-2026-05-29.md`

- [ ] **Step 1: Add a concise feature note**

Create `docs/reports/strategy-tracking-holding-optimizer-2026-05-29.md` with:

```markdown
# 策略跟踪持有期优化说明

## 目标

为每个策略推荐票增加只读复盘指标：最优持有天数、最优退出点、收益/回撤比、利润回吐、以及短线转中长线观察资格。

## 边界

该功能只用于复盘和观察，不回写策略结果、不改变排序、不自动交易、不写入模拟盘账本。

## 防未来函数

- 最优持有天数属于后验复盘指标，页面必须明确显示为复盘指标。
- 短线转中长线资格只按当前可见历史计算，不允许用未来最高点反推早期资格。
- 后端测试覆盖 `hold_extension_state` 不回填到早期 timeline 点。

## 核心字段

- `best_holding_days`
- `best_exit_date`
- `best_exit_return_pct`
- `best_exit_drawdown_pct`
- `return_drawdown_ratio`
- `giveback_from_peak_pct`
- `hold_extension_state`
- `suggested_holding_plan`

## 首版阈值

- 利润垫达到 8% 后才考虑延长持有。
- 最大回撤不能劣于 -6%。
- MA20 不能走弱；数据足够时参考 MA60。
- 利润回吐超过峰值利润 35% 时降级。
```

- [ ] **Step 2: Commit**

Run:

```bash
git add backend/app/services/strategy_tracking_holding.py backend/app/models/schema_defs/strategy_tracking.py backend/app/services/strategy_tracking_builders.py backend/app/services/strategy_tracking.py backend/tests/test_strategy_tracking.py frontend/src/types/strategyTracking.ts frontend/src/features/strategy-tracking/strategyTrackingFormatters.ts frontend/src/features/strategy-tracking/StrategyTrackingTable.tsx frontend/src/features/strategy-tracking/StrategyTrackingDetailDrawer.tsx frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx docs/reports/strategy-tracking-holding-optimizer-2026-05-29.md
git commit -m "feat: add strategy tracking holding optimizer"
```

Expected: commit succeeds.

---

## Acceptance Criteria

- Every recommendation item returns holding optimization fields with safe defaults.
- Best holding metrics are explicitly posterior review metrics and do not affect production execution.
- Hold-extension qualification uses only as-of visible data and has a regression test.
- UI shows best holding days, best exit return, holding bucket, and short-to-midlong state in both list and detail views.
- Refresh endpoint remains read-through and does not mutate strategy output or paper ledger.
- Backend strategy tracking tests pass.
- Frontend strategy tracking tests pass.
- Go BFF tests pass.
- Frontend production build passes.

## Suggested Delivery Order

1. Backend calculator and tests.
2. Backend schema/builder/API fields.
3. Frontend list/detail rendering.
4. BFF/build verification.
5. Documentation and deployment.

## Estimated Time

- Backend calculation and tests: 0.5-1 day.
- Frontend display and tests: 0.5 day.
- Integration verification and deployment: 0.5 day.
- Total: about 1.5-2 days for a reliable first version.
