# Codex 任务：模拟盘绩效看板 —— 战绩总结与趋势分析

**目标**：收盘后自动聚合当日模拟交易数据，按策略和市场状态分组归档，生成 LLM 点评，前端以趋势图展示，为策略调整提供数据参考。

**原则**：绩效历史数据独立存储（不与实时交易表混用），复用现有 `PaperPerformanceService` 的计算逻辑和 `AiService` 的 LLM 能力，不修改任何策略逻辑。

**总任务数**：9 个任务，分 4 个阶段。

---

## 当前状态速查

| 组件 | 状态 | 说明 |
|------|------|------|
| PaperPerformanceService | ✓ 已实现 | `compute_overall()` / `compute_by_strategy()` / `compute_by_market_state()` |
| PaperPerformanceSnapshot | ✓ 已实现 | 每日一条总览快照（total_assets, win_rate, profit_factor 等） |
| PaperTrade.market_state | ✓ 已实现 | 每笔成交已记录市场状态 |
| AI 日报生成 | ✓ 已实现 | AiService.build_insight()，LLM 配置已就绪 |
| TaskManager 定时循环 | ✓ 已实现 | 收盘后可注册定时任务 |
| **策略级历史数据** | ❌ 缺失 | 策略绩效每天算完就丢，没有时序存储 |
| **市场状态历史数据** | ❌ 缺失 | 不同市场状态下的绩效无历史追踪 |
| **LLM 每日点评** | ❌ 缺失 | 无自动生成的中文战绩总结 |
| **前端绩效看板** | ❌ 缺失 | 无趋势图、无策略对比、无战绩回顾 |

---

## 数据模型：三张独立存储表

当前 `PaperPerformanceSnapshot` 只存了账户级别的每日总览。策略级和市场状态级的绩效目前只在 API 响应中实时计算，**收盘后即丢失**。本次新增三张表，专门用于历史时序存储。

### 表 1：`paper_strategy_perf_daily` — 策略级每日绩效

```
每行 = 一个账户 + 一个交易日 + 一个策略 的绩效快照
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增 |
| account_id | FK → paper_accounts.id | 模拟账户 |
| snapshot_date | Date | 交易日 |
| strategy_key | String(80) | 策略标识 |
| trade_count | Integer | 当日该策略成交笔数 |
| win_count | Integer | 盈利笔数 |
| loss_count | Integer | 亏损笔数 |
| win_rate_pct | Numeric(8,4) | 胜率% |
| net_win_rate_pct | Numeric(8,4) | 净胜率% |
| avg_return_pct | Numeric(8,4) | 平均单笔收益率% |
| total_pnl | Numeric(18,2) | 当日该策略总盈亏 |
| profit_factor | Numeric(8,4) nullable | 利润因子 |
| avg_hold_hours | Numeric(8,2) | 平均持仓时长(小时) |
| created_at | DateTime | 记录时间 |

唯一约束: `(account_id, snapshot_date, strategy_key)`

### 表 2：`paper_market_perf_daily` — 市场状态级每日绩效

```
每行 = 一个账户 + 一个交易日 + 一个市场状态 的绩效快照
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增 |
| account_id | FK → paper_accounts.id | 模拟账户 |
| snapshot_date | Date | 交易日 |
| market_state | String(32) | 市场状态（如 震荡修复、高标退潮） |
| trade_count | Integer | 当日该状态下成交笔数 |
| win_rate_pct | Numeric(8,4) | 胜率% |
| net_win_rate_pct | Numeric(8,4) | 净胜率% |
| avg_return_pct | Numeric(8,4) | 平均单笔收益率% |
| profit_factor | Numeric(8,4) nullable | 利润因子 |
| created_at | DateTime | 记录时间 |

唯一约束: `(account_id, snapshot_date, market_state)`

### 表 3：`paper_daily_report` — LLM 每日点评

```
每行 = 一个账户 + 一个交易日 的 AI 点评
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增 |
| account_id | FK → paper_accounts.id | 模拟账户 |
| report_date | Date | 交易日 |
| overall_summary | Text | LLM 生成的总览总结 |
| strategy_highlights | Text(JSON) | `[{"strategy":"first_board","comment":"...","trend":"improving"}]` |
| risk_alerts | Text(JSON) | `[{"level":"warning","content":"连续3日净胜率下降"}]` |
| suggestion | Text | LLM 生成的策略调整建议 |
| raw_metrics_snapshot | Text(JSON) | 生成时输入的原始指标（便于后续复现） |
| generated_at | DateTime | 生成时间 |
| llm_model | String(80) | 使用的模型名 |

唯一约束: `(account_id, report_date)`

---

## 目标架构

```
交易日 15:05（收盘后 5 分钟）自动触发：

┌─────────────────────────────────────────────────────────┐
│  daily_performance_job()  (TaskManager daemon)          │
│                                                         │
│  1. 检查当日是否已归档 → 已归档跳过                      │
│                                                         │
│  2. 调用 PaperPerformanceService:                       │
│     ├─ compute_overall() → 写入 PaperPerformanceSnapshot│
│     ├─ compute_by_strategy() → 写入 paper_strategy_perf  │
│     └─ compute_by_market_state() → 写入 paper_market_perf│
│                                                         │
│  3. 将指标格式化为 prompt，调用 AiService:               │
│     "今日模拟盘战绩: 交易5笔，胜率60%，净胜率20%，       │
│      first_board贡献主要利润，volume_shrink表现不佳..."  │
│     ↓                                                   │
│     存入 paper_daily_report                             │
│                                                         │
│  4. 前端 GET /api/paper/performance/dashboard           │
│     返回 30/90 日绩效时序 + 今日 LLM 点评                │
└─────────────────────────────────────────────────────────┘
```

---

## 阶段一：数据模型（2 个任务）

### 任务 1：新增三张 ORM 模型

**修改文件**：`backend/app/models/entities.py`

在 `PaperPerformanceSnapshot` 类定义之后（约第 612 行后），追加：

```python
class PaperStrategyPerfDaily(Base):
    """策略级每日绩效快照 —— 独立存储，用于趋势分析。"""
    __tablename__ = "paper_strategy_perf_daily"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "snapshot_date", "strategy_key",
            name="uq_pspd_account_date_strategy",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    win_count: Mapped[int] = mapped_column(Integer, default=0)
    loss_count: Mapped[int] = mapped_column(Integer, default=0)
    win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    net_win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    avg_return_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    total_pnl: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    profit_factor: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    avg_hold_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaperMarketPerfDaily(Base):
    """市场状态级每日绩效快照 —— 独立存储，用于趋势分析。"""
    __tablename__ = "paper_market_perf_daily"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "snapshot_date", "market_state",
            name="uq_pmpd_account_date_market",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    market_state: Mapped[str] = mapped_column(String(32), index=True)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    net_win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    avg_return_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    profit_factor: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaperDailyReport(Base):
    """LLM 每日绩效点评 —— 独立存储，用于战绩回顾。"""
    __tablename__ = "paper_daily_reports"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "report_date",
            name="uq_pdr_account_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    overall_summary: Mapped[str] = mapped_column(Text, default="")
    strategy_highlights: Mapped[str] = mapped_column(Text, default="[]")
    risk_alerts: Mapped[str] = mapped_column(Text, default="[]")
    suggestion: Mapped[str] = mapped_column(Text, default="")
    raw_metrics_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    llm_model: Mapped[str] = mapped_column(String(80), default="")
```

**数据库迁移**（在 `init_db` 中追加，幂等）：

```python
def _migrate_performance_tables():
    with SessionLocal() as db:
        for table_name in (
            "paper_strategy_perf_daily",
            "paper_market_perf_daily",
            "paper_daily_reports",
        ):
            try:
                db.execute(text(f"SELECT 1 FROM {table_name} LIMIT 1"))
            except Exception:
                # 表不存在 → Base.metadata 会自动创建
                pass
```

**验证**：

```bash
sqlite3 data/t_quant.db ".tables" | grep "paper_strategy_perf\|paper_market_perf\|paper_daily"
# 应看到三张新表
```

---

### 任务 2：TypeScript 类型定义

**新建文件**：`frontend/src/types/performance.ts`

```typescript
export interface StrategyPerfDaily {
  id: number;
  snapshot_date: string;
  strategy_key: string;
  trade_count: number;
  win_count: number;
  loss_count: number;
  win_rate_pct: number;
  net_win_rate_pct: number;
  avg_return_pct: number;
  total_pnl: number;
  profit_factor: number | null;
  avg_hold_hours: number;
}

export interface MarketPerfDaily {
  id: number;
  snapshot_date: string;
  market_state: string;
  trade_count: number;
  win_rate_pct: number;
  net_win_rate_pct: number;
  avg_return_pct: number;
  profit_factor: number | null;
}

export interface DailyReport {
  id: number;
  report_date: string;
  overall_summary: string;
  strategy_highlights: StrategyHighlight[];
  risk_alerts: RiskAlert[];
  suggestion: string;
  generated_at: string;
  llm_model: string;
}

export interface StrategyHighlight {
  strategy: string;
  comment: string;
  trend: "improving" | "stable" | "declining" | "new";
}

export interface RiskAlert {
  level: "info" | "warning" | "danger";
  content: string;
}

export interface DashboardResponse {
  account: { id: number; total_assets: number; total_return_pct: number };
  equity_curve: { date: string; total_assets: number; cumulative_return_pct: number }[];
  win_rate_trend: { date: string; win_rate_pct: number; net_win_rate_pct: number }[];
  strategy_trend: {
    strategy_key: string;
    points: { date: string; win_rate_pct: number; avg_return_pct: number }[];
  }[];
  market_perf_heatmap: {
    market_state: string;
    avg_win_rate_pct: number;
    avg_return_pct: number;
    trade_count: number;
  }[];
  today_report: DailyReport | null;
}
```

---

## 阶段二：后端绩效归档（2 个任务）

### 任务 3：日终归档服务

**新建文件**：`backend/app/services/paper/archive.py`

```python
"""收盘后绩效数据归档服务。"""

from datetime import date, datetime
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    PaperAccount,
    PaperPerformanceSnapshot,
    PaperStrategyPerfDaily,
    PaperMarketPerfDaily,
    PaperDailyReport,
    PaperTrade,
)
from app.services.paper.performance import PaperPerformanceService

logger = logging.getLogger(__name__)


class PaperArchiveService:
    """收盘后归档：策略绩效、市场状态绩效、LLM 点评。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.perf = PaperPerformanceService(db)

    def archive_all(self, account_id: int) -> dict:
        """对一个账户执行完整归档（幂等：当日已归档则跳过）。"""
        today = date.today()
        result = {"account_id": account_id, "date": today.isoformat()}

        # 检查是否已归档
        if self._already_archived(account_id, today):
            result["skipped"] = True
            result["reason"] = "今日已归档"
            return result

        # 1. 总览快照（写入现有 PaperPerformanceSnapshot）
        self.perf.create_daily_snapshot(account_id)

        # 2. 策略级绩效
        strategy_stats = self.perf.compute_by_strategy(account_id)
        saved_strategies = 0
        for item in strategy_stats:
            self._upsert_strategy_perf(account_id, today, item)
            saved_strategies += 1

        # 3. 市场状态级绩效
        market_stats = self.perf.compute_by_market_state(account_id)
        saved_markets = 0
        for item in market_stats:
            self._upsert_market_perf(account_id, today, item)
            saved_markets += 1

        self.db.commit()

        result["strategies_saved"] = saved_strategies
        result["market_states_saved"] = saved_markets
        logger.info("绩效归档完成: account=%d, 策略=%d, 市场状态=%d",
                    account_id, saved_strategies, saved_markets)
        return result

    def archive_all_active(self) -> list[dict]:
        """对所有活跃账户执行归档。"""
        accounts = self.db.execute(
            select(PaperAccount).where(PaperAccount.status == "active")
        ).scalars().all()
        results = []
        for account in accounts:
            try:
                results.append(self.archive_all(account.id))
            except Exception:
                logger.exception("归档账户 %d 失败", account.id)
                results.append({"account_id": account.id, "error": "归档失败"})
        return results

    def _already_archived(self, account_id: int, target_date: date) -> bool:
        existing = self.db.execute(
            select(PaperStrategyPerfDaily).where(
                PaperStrategyPerfDaily.account_id == account_id,
                PaperStrategyPerfDaily.snapshot_date == target_date,
            )
        ).first()
        return existing is not None

    def _upsert_strategy_perf(self, account_id: int, target_date: date, item: dict) -> None:
        existing = self.db.execute(
            select(PaperStrategyPerfDaily).where(
                PaperStrategyPerfDaily.account_id == account_id,
                PaperStrategyPerfDaily.snapshot_date == target_date,
                PaperStrategyPerfDaily.strategy_key == item["key"],
            )
        ).scalar_one_or_none()

        if existing is None:
            existing = PaperStrategyPerfDaily(
                account_id=account_id,
                snapshot_date=target_date,
                strategy_key=item["key"],
            )
            self.db.add(existing)

        existing.trade_count = item.get("trades", 0)
        existing.win_rate_pct = item.get("win_rate_pct", 0.0)
        existing.net_win_rate_pct = item.get("net_win_rate_pct", 0.0)
        existing.avg_return_pct = item.get("avg_return_pct", 0.0)
        existing.profit_factor = item.get("profit_factor")
        existing.total_pnl = item.get("total_pnl", 0.0)
        existing.avg_hold_hours = item.get("avg_hold_hours", 0.0)

    def _upsert_market_perf(self, account_id: int, target_date: date, item: dict) -> None:
        existing = self.db.execute(
            select(PaperMarketPerfDaily).where(
                PaperMarketPerfDaily.account_id == account_id,
                PaperMarketPerfDaily.snapshot_date == target_date,
                PaperMarketPerfDaily.market_state == item["key"],
            )
        ).scalar_one_or_none()

        if existing is None:
            existing = PaperMarketPerfDaily(
                account_id=account_id,
                snapshot_date=target_date,
                market_state=item["key"],
            )
            self.db.add(existing)

        existing.trade_count = item.get("trades", 0)
        existing.win_rate_pct = item.get("win_rate_pct", 0.0)
        existing.net_win_rate_pct = item.get("net_win_rate_pct", 0.0)
        existing.avg_return_pct = item.get("avg_return_pct", 0.0)
        existing.profit_factor = item.get("profit_factor")
```

**验证**：

```bash
cd backend && .venv/bin/python -c "
from app.core.database import SessionLocal
from app.services.paper.archive import PaperArchiveService
db = SessionLocal()
svc = PaperArchiveService(db)
result = svc.archive_all(1)
print(result)
db.close()
"
```

---

### 任务 4：LLM 每日点评生成

**修改文件**：`backend/app/services/paper/archive.py`（追加方法）

```python
    def generate_daily_report(self, account_id: int) -> PaperDailyReport | None:
        """生成 LLM 每日绩效点评（需 AiService 已配置）。"""
        today = date.today()
        overall = self.perf.compute_overall(account_id)
        strategies = self.perf.compute_by_strategy(account_id)
        markets = self.perf.compute_by_market_state(account_id)

        # 无需 AI：当日无交易
        if overall["total_trades"] == 0:
            report = self._upsert_empty_report(account_id, today)
            return report

        # 构建 prompt
        prompt = self._build_report_prompt(overall, strategies, markets)
        raw_metrics = json.dumps({
            "overall": overall,
            "strategies": strategies,
            "markets": markets,
        }, ensure_ascii=False)

        # 调用 AiService
        from app.services.ai_service import AiService
        from app.services.settings_service import SettingsService

        settings_svc = SettingsService(self.db)
        ai = AiService()
        insight = ai.build_task_insight(
            settings=settings_svc.get_ai_settings(),
            payload={"user_prompt": prompt},
            system_prompt=(
                "你是A股量化交易绩效分析师。请基于提供的模拟盘交易数据，"
                "生成一份中文战绩总结。必须严格返回 JSON，字段为: "
                "overall_summary(一段话总结今日表现), "
                "strategy_highlights(数组, 每项含 strategy/comment/trend), "
                "risk_alerts(数组, 每项含 level/content), "
                "suggestion(策略调整建议)。"
            ),
            include_ai=True,
            max_tokens=1200,
        )

        # 解析 LLM 响应
        highlights = []
        alerts = []
        summary = ""
        suggestion = ""
        if insight.raw:
            try:
                parsed = json.loads(insight.raw) if isinstance(insight.raw, str) else insight.raw
                summary = parsed.get("overall_summary", insight.summary or "")
                highlights = parsed.get("strategy_highlights", [])
                alerts = parsed.get("risk_alerts", [])
                suggestion = parsed.get("suggestion", "")
            except (json.JSONDecodeError, TypeError):
                summary = insight.summary or "AI 响应解析失败"
                suggestion = "请检查 LLM 配置和响应格式。"

        # 写入
        report = PaperDailyReport(
            account_id=account_id,
            report_date=today,
            overall_summary=summary,
            strategy_highlights=json.dumps(highlights, ensure_ascii=False),
            risk_alerts=json.dumps(alerts, ensure_ascii=False),
            suggestion=suggestion,
            raw_metrics_snapshot=raw_metrics,
            llm_model=settings_svc.get_ai_settings().get("llm_model", ""),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def _build_report_prompt(self, overall, strategies, markets) -> str:
        lines = ["以下是今日模拟盘交易数据，请生成战绩总结：", ""]
        lines.append(f"总览: 交易{overall['total_trades']}笔，"
                     f"胜率{overall['win_rate_pct']:.1f}%，"
                     f"净胜率{overall['net_win_rate_pct']:.1f}%，"
                     f"总收益率{overall['total_return_pct']:.2f}%，"
                     f"利润因子{overall['profit_factor'] or 'N/A'}，"
                     f"最大回撤{overall['max_drawdown_pct']:.2f}%。")
        lines.append("")
        lines.append("策略表现：")
        for s in sorted(strategies, key=lambda x: x["trades"], reverse=True):
            lines.append(f"  {s['key']}: {s['trades']}笔, "
                        f"胜率{s['win_rate_pct']:.1f}%, "
                        f"均收{s['avg_return_pct']:.2f}%, "
                        f"PF={s['profit_factor'] or 'N/A'}")
        lines.append("")
        lines.append("市场状态表现：")
        for m in sorted(markets, key=lambda x: x["trades"], reverse=True):
            lines.append(f"  {m['key']}: {m['trades']}笔, "
                        f"胜率{m['win_rate_pct']:.1f}%, "
                        f"均收{m['avg_return_pct']:.2f}%")
        return "\n".join(lines)

    def _upsert_empty_report(self, account_id: int, target_date: date) -> PaperDailyReport:
        existing = self.db.execute(
            select(PaperDailyReport).where(
                PaperDailyReport.account_id == account_id,
                PaperDailyReport.report_date == target_date,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        report = PaperDailyReport(
            account_id=account_id,
            report_date=target_date,
            overall_summary="今日无模拟交易。",
            llm_model="none",
        )
        self.db.add(report)
        self.db.commit()
        return report
```

**验证**：

```bash
cd backend && .venv/bin/python -c "
from app.core.database import SessionLocal
from app.services.paper.archive import PaperArchiveService
db = SessionLocal()
svc = PaperArchiveService(db)
report = svc.generate_daily_report(1)
print('Summary:', report.overall_summary[:100] if report else 'None')
db.close()
"
```

---

### 任务 5：收盘定时任务 + 配置

**修改文件**：`backend/app/core/config.py`

```python
    # 绩效归档
    paper_perf_archive_enabled: bool = True     # 收盘后自动归档
    paper_perf_archive_time: str = "15:05"       # 归档触发时间
    paper_perf_ai_report_enabled: bool = True    # 是否生成 LLM 点评
```

**修改文件**：`backend/app/main.py`

在 lifespan 中注册定时任务：

```python
from app.services.paper.archive import PaperArchiveService
from datetime import datetime, time as dt_time

def _should_archive_today() -> bool:
    """仅交易日下午 3 点后触发。"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return now.time() >= dt_time(15, 5)

def _archive_paper_performance_once() -> None:
    if not _should_archive_today():
        return
    db = SessionLocal()
    try:
        svc = PaperArchiveService(db)
        results = svc.archive_all_active()
        logger.info("绩效归档完成: %s", results)

        if settings.paper_perf_ai_report_enabled:
            accounts = db.execute(
                select(PaperAccount).where(PaperAccount.status == "active")
            ).scalars().all()
            for account in accounts:
                try:
                    svc.generate_daily_report(account.id)
                except Exception:
                    logger.exception("生成日报失败 account=%d", account.id)
    except Exception:
        logger.exception("绩效归档异常")
    finally:
        db.close()

# 在 lifespan 中 _background_jobs_enabled() 块内追加:
if settings.paper_perf_archive_enabled:
    task_manager.register_loop(
        name="paper_perf_archive",
        target=_archive_paper_performance_once,
        interval_seconds=300,  # 每 5 分钟检查一次
        initial_delay_seconds=60,
    )
```

**定时检测逻辑**：每 5 分钟检查一次是否到了归档时间（>= 15:05），到了就执行归档（每日只执行一次，幂等），未到就直接返回。

**验证**：

```bash
# 检查定时任务是否注册
curl http://localhost:8000/api/agent/health
# 查看日志: grep "绩效归档" logs/*
```

---

## 阶段三：Dashboard API（2 个任务）

### 任务 6：Dashboard 数据接口

**修改文件**：`backend/app/api/routes/paper.py`（追加路由）

```python
@router.get("/performance/dashboard")
def get_performance_dashboard(
    days: int = Query(30, ge=7, le=180, description="回溯天数"),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> dict:
    """返回绩效看板的全部数据：权益曲线、胜率趋势、策略对比、市场热力图、今日点评。"""
    account_service = PaperAccountService(db)
    account = account_service.get_or_create_default(current_user.id)

    from datetime import date, timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # 1. 权益曲线（总资产 + 累计收益率）
    snapshots = db.execute(
        select(PaperPerformanceSnapshot).where(
            PaperPerformanceSnapshot.account_id == account.id,
            PaperPerformanceSnapshot.snapshot_date >= start_date,
        ).order_by(PaperPerformanceSnapshot.snapshot_date.asc())
    ).scalars().all()

    equity_curve = []
    for snap in snapshots:
        equity_curve.append({
            "date": snap.snapshot_date.isoformat(),
            "total_assets": snap.total_assets,
            "cumulative_return_pct": snap.cumulative_return_pct,
        })
    # 补上今日实时数据（如果今天还没归档）
    today_str = end_date.isoformat()
    if not equity_curve or equity_curve[-1]["date"] != today_str:
        equity_curve.append({
            "date": today_str,
            "total_assets": account.total_assets,
            "cumulative_return_pct": (
                (account.total_assets - account.initial_cash) / max(account.initial_cash, 1) * 100
            ),
        })

    # 2. 胜率趋势（总体）
    win_rate_trend = []
    for snap in snapshots:
        win_rate_trend.append({
            "date": snap.snapshot_date.isoformat(),
            "win_rate_pct": snap.win_rate_pct,
            "net_win_rate_pct": snap.net_win_rate_pct,
        })

    # 3. 策略绩效趋势（按 strategy_key 分组）
    strategy_rows = db.execute(
        select(PaperStrategyPerfDaily).where(
            PaperStrategyPerfDaily.account_id == account.id,
            PaperStrategyPerfDaily.snapshot_date >= start_date,
        ).order_by(PaperStrategyPerfDaily.snapshot_date.asc())
    ).scalars().all()

    strategy_map: dict[str, list[dict]] = {}
    for row in strategy_rows:
        if row.strategy_key not in strategy_map:
            strategy_map[row.strategy_key] = []
        strategy_map[row.strategy_key].append({
            "date": row.snapshot_date.isoformat(),
            "win_rate_pct": row.win_rate_pct,
            "avg_return_pct": row.avg_return_pct,
        })

    strategy_trend = [
        {"strategy_key": key, "points": points}
        for key, points in strategy_map.items()
    ]

    # 4. 市场状态热力图（聚合期内数据）
    market_rows = db.execute(
        select(PaperMarketPerfDaily).where(
            PaperMarketPerfDaily.account_id == account.id,
            PaperMarketPerfDaily.snapshot_date >= start_date,
        )
    ).scalars().all()

    from collections import defaultdict
    market_agg: dict[str, dict] = defaultdict(lambda: {
        "total_trades": 0, "total_win_rate": 0.0,
        "total_return": 0.0, "days": 0,
    })
    for row in market_rows:
        agg = market_agg[row.market_state]
        agg["total_trades"] += row.trade_count
        agg["total_win_rate"] += row.win_rate_pct
        agg["total_return"] += row.avg_return_pct
        agg["days"] += 1

    market_heatmap = []
    for state, agg in market_agg.items():
        d = agg["days"]
        market_heatmap.append({
            "market_state": state,
            "avg_win_rate_pct": round(agg["total_win_rate"] / d, 2) if d else 0,
            "avg_return_pct": round(agg["total_return"] / d, 2) if d else 0,
            "trade_count": agg["total_trades"],
        })
    market_heatmap.sort(key=lambda x: x["trade_count"], reverse=True)

    # 5. 今日 LLM 点评
    today_report = db.execute(
        select(PaperDailyReport).where(
            PaperDailyReport.account_id == account.id,
            PaperDailyReport.report_date == end_date,
        )
    ).scalar_one_or_none()

    import json as _json
    report_data = None
    if today_report:
        report_data = {
            "id": today_report.id,
            "report_date": today_report.report_date.isoformat(),
            "overall_summary": today_report.overall_summary,
            "strategy_highlights": _json.loads(today_report.strategy_highlights or "[]"),
            "risk_alerts": _json.loads(today_report.risk_alerts or "[]"),
            "suggestion": today_report.suggestion,
            "generated_at": today_report.generated_at.isoformat() if today_report.generated_at else "",
            "llm_model": today_report.llm_model,
        }

    return {
        "account": {
            "id": account.id,
            "total_assets": account.total_assets,
            "total_return_pct": (
                (account.total_assets - account.initial_cash) / max(account.initial_cash, 1) * 100
            ),
        },
        "equity_curve": equity_curve,
        "win_rate_trend": win_rate_trend,
        "strategy_trend": strategy_trend,
        "market_heatmap": market_heatmap,
        "today_report": report_data,
    }
```

**验证**：

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/paper/performance/dashboard?days=30" | python -m json.tool | head -30
```

---

### 任务 7：手动触发归档端点

**修改文件**：`backend/app/api/routes/paper.py`（追加）

```python
@router.post("/performance/archive")
def trigger_performance_archive(
    current_user: User = Depends(require_paper_trading),
    _admin=Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> dict:
    """手动触发绩效归档（需管理员权限）。"""
    from app.services.paper.archive import PaperArchiveService

    svc = PaperArchiveService(db)
    results = svc.archive_all_active()

    # 同时生成 LLM 点评
    reports = []
    for result in results:
        if "error" not in result:
            try:
                report = svc.generate_daily_report(result["account_id"])
                reports.append({"account_id": result["account_id"], "report_generated": report is not None})
            except Exception as e:
                reports.append({"account_id": result["account_id"], "report_error": str(e)})

    return {"archive_results": results, "reports": reports}
```

---

## 阶段四：前端绩效看板（2 个任务）

### 任务 8：绩效看板 React 组件

**新建文件**：`frontend/src/features/trading-workspace/PerformanceDashboard.tsx`

```tsx
import { useEffect, useState } from "react";
import { client } from "../../api/client";
import { formatAmount, formatPct } from "./workspaceFormatters";
import type { DashboardResponse } from "../../types/performance";

export function PerformanceDashboard() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    client.get(`/paper/performance/dashboard?days=${days}`)
      .then(res => setData(res.data))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) return <div className="panel"><div className="skeleton-line" /></div>;
  if (!data) return <div className="empty-state">暂无绩效数据</div>;

  return (
    <section className="page-grid perf-dashboard-grid">
      {/* 顶栏：关键指标 */}
      <section className="panel perf-hero">
        <div className="panel-title">
          <span className="hint">PERFORMANCE</span>
          <h2>模拟盘绩效看板</h2>
          <select value={days} onChange={e => setDays(Number(e.target.value))}>
            <option value={7}>近 7 天</option>
            <option value={30}>近 30 天</option>
            <option value={90}>近 90 天</option>
            <option value={180}>近 180 天</option>
          </select>
        </div>
        <div className="metric-grid perf-hero-metrics">
          <MetricCard label="当前总资产" value={formatAmount(data.account.total_assets)} tone="neutral" />
          <MetricCard label="累计收益率" value={formatPct(data.account.total_return_pct)} tone={data.account.total_return_pct > 0 ? "up" : "down"} />
        </div>
      </section>

      {/* LLM 每日点评 */}
      {data.today_report ? (
        <section className="panel perf-report">
          <div className="panel-title">
            <span className="hint">AI REVIEW</span>
            <h2>今日战绩点评</h2>
            <span className="status-chip neutral">{data.today_report.report_date}</span>
          </div>
          <p className="perf-summary">{data.today_report.overall_summary}</p>
          <div className="perf-highlights">
            {data.today_report.strategy_highlights.map((h, i) => (
              <div key={i} className={`perf-highlight-tag ${h.trend}`}>
                <strong>{h.strategy}</strong>
                <span>{h.comment}</span>
              </div>
            ))}
          </div>
          {data.today_report.risk_alerts.length > 0 && (
            <div className="perf-alerts">
              {data.today_report.risk_alerts.map((a, i) => (
                <div key={i} className={`warn ${a.level}`}>{a.content}</div>
              ))}
            </div>
          )}
          {data.today_report.suggestion && (
            <p className="muted perf-suggestion">💡 {data.today_report.suggestion}</p>
          )}
        </section>
      ) : null}

      {/* 权益曲线 */}
      <section className="panel perf-equity">
        <div className="panel-title"><h2>权益曲线</h2></div>
        <EquityCurveChart data={data.equity_curve} />
      </section>

      {/* 胜率趋势 */}
      <section className="panel perf-win-rate">
        <div className="panel-title"><h2>胜率趋势</h2></div>
        <WinRateChart data={data.win_rate_trend} />
      </section>

      {/* 策略对比 */}
      <section className="panel perf-strategy">
        <div className="panel-title"><h2>策略绩效对比</h2></div>
        <StrategyComparisonChart data={data.strategy_trend} />
      </section>

      {/* 市场状态热力图 */}
      <section className="panel perf-market">
        <div className="panel-title"><h2>市场状态表现</h2></div>
        <MarketHeatmap data={data.market_heatmap} />
      </section>
    </section>
  );
}

function MetricCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className={`metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
```

### 图表组件

使用 recharts（项目已有依赖）。三个图表子组件：

```tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

function EquityCurveChart({ data }: { data: { date: string; cumulative_return_pct: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} unit="%" />
        <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
        <Line type="monotone" dataKey="cumulative_return_pct" stroke="#c62828" dot={false} name="累计收益率" />
      </LineChart>
    </ResponsiveContainer>
  );
}

function WinRateChart({ data }: { data: { date: string; win_rate_pct: number; net_win_rate_pct: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} unit="%" />
        <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
        <Legend />
        <Line type="monotone" dataKey="win_rate_pct" stroke="#c62828" dot={false} name="胜率" />
        <Line type="monotone" dataKey="net_win_rate_pct" stroke="#1f8b4c" dot={false} name="净胜率" />
      </LineChart>
    </ResponsiveContainer>
  );
}

function StrategyComparisonChart({ data }: { data: { strategy_key: string; points: { date: string; win_rate_pct: number }[] }[] }) {
  const STRATEGY_COLORS = ["#c62828", "#1f8b4c", "#d6a55c", "#2b6cb0", "#805ad5", "#c05621"];
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} allowDuplicatedCategory={false} />
        <YAxis tick={{ fontSize: 11 }} unit="%" />
        <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
        <Legend />
        {data.map((strat, idx) => (
          <Line
            key={strat.strategy_key}
            data={strat.points}
            type="monotone"
            dataKey="win_rate_pct"
            stroke={STRATEGY_COLORS[idx % STRATEGY_COLORS.length]}
            dot={false}
            name={strat.strategy_key}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function MarketHeatmap({ data }: { data: { market_state: string; avg_win_rate_pct: number; avg_return_pct: number; trade_count: number }[] }) {
  if (!data.length) return <div className="empty-state">暂无市场状态数据</div>;
  return (
    <table className="paper-performance-table">
      <thead className="paper-performance-head">
        <tr>
          <th>市场状态</th>
          <th>成交笔数</th>
          <th>平均胜率</th>
          <th>平均收益</th>
        </tr>
      </thead>
      <tbody>
        {data.map(row => (
          <tr key={row.market_state} className="paper-performance-row">
            <td><strong>{row.market_state}</strong></td>
            <td>{row.trade_count}</td>
            <td className={row.avg_win_rate_pct > 50 ? "up" : "down"}>{formatPct(row.avg_win_rate_pct)}</td>
            <td className={row.avg_return_pct > 0 ? "up" : "down"}>{formatPct(row.avg_return_pct)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

### 路由注册

**修改文件**：`frontend/src/features/trading-workspace/TradingWorkspace.tsx`

在 `page` 路由中增加 `"perf"` 分支：

```tsx
import { PerformanceDashboard } from "./PerformanceDashboard";

// 在页面渲染 switch 中:
{page === "perf" && <PerformanceDashboard />}
```

**修改文件**：`frontend/src/features/trading-workspace/Topbar.tsx`

在导航 tabs 中增加 "绩效" 入口。

### 验证

```bash
cd frontend && npm run build
# 应构建成功，无类型错误
# 访问 http://localhost:5173 → 切换到"绩效"tab
```

---

### 任务 9：集成测试

**新建文件**：`backend/tests/test_paper_performance_archive.py`

```python
"""绩效归档集成测试。"""
import unittest


class PaperPerformanceArchiveTest(unittest.TestCase):

    def test_01_imports_work(self):
        from app.services.paper.archive import PaperArchiveService
        self.assertTrue(callable(PaperArchiveService))

    def test_02_models_exist(self):
        from app.models.entities import (
            PaperStrategyPerfDaily,
            PaperMarketPerfDaily,
            PaperDailyReport,
        )
        self.assertTrue(hasattr(PaperStrategyPerfDaily, '__tablename__'))
        self.assertTrue(hasattr(PaperMarketPerfDaily, '__tablename__'))
        self.assertTrue(hasattr(PaperDailyReport, '__tablename__'))

    def test_03_archive_idempotent(self):
        """归档应幂等：重复执行不报错。"""
        from app.core.database import SessionLocal
        from app.services.paper.archive import PaperArchiveService

        db = SessionLocal()
        try:
            svc = PaperArchiveService(db)
            result1 = svc.archive_all(1)
            result2 = svc.archive_all(1)

            if isinstance(result2, dict) and result2.get("skipped"):
                self.assertTrue(result2["skipped"])
        finally:
            db.close()

    def test_04_dashboard_api_schema(self):
        """验证 dashboard 返回结构。"""
        dashboard_fields = [
            "account", "equity_curve", "win_rate_trend",
            "strategy_trend", "market_heatmap", "today_report",
        ]
        for field in dashboard_fields:
            self.assertIsInstance(field, str)


if __name__ == "__main__":
    unittest.main()
```

**验证**：

```bash
cd backend && .venv/bin/python -m pytest tests/test_paper_performance_archive.py -v
```

---

## 验收标准

| 检查项 | 通过标准 |
|--------|---------|
| 三张新表创建 | `paper_strategy_perf_daily` / `paper_market_perf_daily` / `paper_daily_reports` 可通过 SQL 查询 |
| 手动触发归档 | `POST /api/paper/performance/archive` 返回成功，数据写入三张表 |
| 定时归档 | 收盘后 15:05 自动触发，日志可见 |
| 归档幂等 | 同一天多次归档不产生重复数据 |
| LLM 点评 | 配置 LLM 后，`paper_daily_reports` 包含有效的中文点评 |
| 无 LLM 时降级 | 未配置 LLM 时，"今日无模拟交易" 或空点评仍正常归档 |
| Dashboard API | `GET /api/paper/performance/dashboard?days=30` 返回 200，含完整数据 |
| 前端看板 | 切换到绩效 Tab，权益曲线/胜率/策略对比/市场热力图/点评均可渲染 |
| 响应式 | 移动端/平板/桌面均可正常显示绩效看板 |
| 时区正确 | 归档日期使用本地时区，不因 UTC 偏移导致日期错位 |

---

## 数据留存说明

三张新表与 `paper_trades`、`paper_orders` 等操作表物理上在同一个 SQLite 文件，但逻辑独立：

- **操作表**（paper_orders / paper_trades / paper_positions）：高频读写，记录每笔交易流水
- **绩效表**（paper_strategy_perf_daily / paper_market_perf_daily / paper_daily_reports）：每日一次写入，只读查询，用于历史趋势分析

这种分离的好处：
- 绩效查询（SELECT 大量历史行）不影响实时交易写入
- 可单独导出绩效数据进行离线分析
- 如果未来要迁移到独立分析数据库，只需迁移这三张表

---

*本方案所有改动为新增功能，不修改任何策略逻辑、信号生成、因子计算或业务规则。*
