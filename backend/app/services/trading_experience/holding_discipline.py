from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.services.trading_experience import repository
from app.services.trading_experience.key_level_context import key_level_missing_evidence, load_stock_key_level_context
from app.services.trading_experience.schemas import HoldingDisciplineHint


def build_hints(
    db: Session,
    *,
    account_id: int | None = None,
    user_id: int | None = None,
) -> tuple[int | None, list[HoldingDisciplineHint]]:
    account = repository.active_paper_account(db, account_id, user_id=user_id)
    if not account:
        return account_id, []
    as_of = datetime.now()
    hints: list[HoldingDisciplineHint] = []
    for position in repository.paper_positions(db, account.id):
        latest = float(position.latest_price or 0.0)
        cost = float(position.cost_basis or 0.0)
        pnl_pct = float(position.unrealized_pnl_pct or 0.0)
        if latest <= 0 or cost <= 0:
            hints.append(_hint(account.id, position.symbol, "watch_cadence", "info", ["持仓或行情数据不足"], "insufficient", as_of))
            continue
        key_level = load_stock_key_level_context(db, position.symbol, latest_price=latest)
        if key_level is None:
            hints.append(
                _hint(
                    account.id,
                    position.symbol,
                    "watch_cadence",
                    "info",
                    key_level_missing_evidence(position.symbol),
                    "insufficient",
                    as_of,
                )
            )
            continue
        evidence = [
            *key_level.evidence,
            f"现价 {latest:.2f}",
            f"浮动收益 {pnl_pct:.2f}%",
        ]
        if pnl_pct >= 5:
            hints.append(_hint(account.id, position.symbol, "trailing_stop", "info", evidence, key_level.result.data_quality, as_of))
        if key_level.support_broken:
            hints.append(_hint(account.id, position.symbol, "break_down", "warn", evidence, key_level.result.data_quality, as_of))
            hints.append(
                _hint(
                    account.id,
                    position.symbol,
                    "no_add_down_warning",
                    "warn",
                    [*evidence, "AKeyLevel 客观支撑已跌破，纪律日志仅记录风险"],
                    key_level.result.data_quality,
                    as_of,
                )
            )
        elif pnl_pct < -3 and key_level.near_support:
            hints.append(_hint(account.id, position.symbol, "emotional_pullback", "warn", evidence, key_level.result.data_quality, as_of))
        else:
            hints.append(_hint(account.id, position.symbol, "watch_cadence", "info", [*key_level.evidence, "持仓结构未触发纪律风险"], key_level.result.data_quality, as_of))
    return account.id, hints


def _hint(account_id: int, symbol: str, code: str, level: str, evidence: list[str], data_quality: str, as_of: datetime) -> HoldingDisciplineHint:
    return HoldingDisciplineHint(
        account_id=account_id,
        symbol=symbol,
        hint_code=code,  # type: ignore[arg-type]
        level=level,  # type: ignore[arg-type]
        evidence=evidence,
        data_quality=data_quality,  # type: ignore[arg-type]
        as_of=as_of,
    )
