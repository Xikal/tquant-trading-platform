from __future__ import annotations

from datetime import datetime

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.entities import (
    DailyBarSnapshot,
    Instrument,
    StrategyMetadata,
    StrategyPreset,
    StrategyTierOverride,
    StrategyTierOverrideLog,
    User,
)
from app.models.schema_defs.strategy_meta import (
    StrategyMetaOut,
    StrategyMetaResponse,
    StrategyGovernanceMutationRequest,
    StrategyGovernanceMutationResponse,
    StrategyPresetOut,
    StrategyPresetResponse,
    SymbolSearchItem,
    SymbolSearchResponse,
)
from app.services.low_buy.strategy_policy import StrategyTier, get_strategy_tier
from app.services.low_buy.strategy_tier_resolver import StrategyTierResolver, clear_strategy_tier_cache
from app.services.low_buy.strategy_governance import latest_strategy_performance_map, _strategy_health
from app.services.strategy_metadata_defaults import (
    ADMIN_ROLES,
    DEFAULT_PRESETS,
    DEFAULT_STRATEGY_META,
    DEFAULT_STRATEGY_SEEDS_BY_KEY,
    FACTOR_ACCESS_ROLES,
    RESEARCH_ACCESS_ROLES,
    RESEARCH_TO_AUXILIARY_GATED_STRATEGIES,
    RESEARCH_TO_AUXILIARY_MIN_FILLED,
    RESEARCH_TO_AUXILIARY_MIN_HEALTH,
    StrategyDisplaySeed,
)
from app.services.strategy_metadata_helpers import (
    display_category as _display_category,
    escape_like as _escape_like,
    filter_preset as _filter_preset,
    has_any_role as _has_any_role,
    metadata_fallback_tier as _metadata_fallback_tier,
    normalize_tier as _normalize_tier,
    preset_from_row as _preset_from_row,
    preset_from_seed as _preset_from_seed,
    promotion_readiness_fields as _promotion_readiness_fields,
    roles as _roles,
    row_bool as _row_bool,
    row_text as _row_text,
    strategy_feature_enabled as _strategy_feature_enabled,
    strategy_tier as _strategy_tier,
)

class StrategyMetadataService:
    def __init__(self, db: Session):
        self.db = db

    def list_strategy_meta(
        self,
        *,
        current_user: User | None = None,
        include_hidden: bool = False,
    ) -> StrategyMetaResponse:
        overrides = self._load_metadata_overrides()
        resolver = self._tier_resolver()
        roles = _roles(current_user)
        can_view_factor = _has_any_role(roles, FACTOR_ACCESS_ROLES)
        can_view_backtest_only = _has_any_role(roles, RESEARCH_ACCESS_ROLES)
        can_view_hidden = include_hidden and _has_any_role(roles, ADMIN_ROLES)
        performance_map = latest_strategy_performance_map(self.db)
        items = []
        for seed in DEFAULT_STRATEGY_META:
            row = overrides.get(seed.key)
            tier = resolver.resolve(seed.key, fallback=_strategy_tier(seed))
            display_category = _display_category(row.category if row else "", tier)
            metadata_enabled = _row_bool(getattr(row, "enabled", None), seed.enabled) if row else seed.enabled
            item = StrategyMetaOut(
                key=seed.key,
                name=row.display_name if row else seed.name,
                display_name=row.display_name if row else seed.name,
                description=row.description if row and row.description else seed.description,
                tier=tier.value,
                category_key=tier.value,
                category=display_category,
                display_category=display_category,
                risk_level=row.risk_level if row and row.risk_level else seed.risk_level,
                typical_holding_days=(
                    row.typical_holding_days if row and row.typical_holding_days else seed.typical_holding_days
                ),
                sort_order=row.sort_order if row else seed.sort_order,
                enabled=metadata_enabled and _strategy_feature_enabled(self.db, seed.key, default=metadata_enabled),
                probe_status=_row_text(getattr(row, "probe_status", None), seed.probe_status) if row else seed.probe_status,
                probe_summary=_row_text(getattr(row, "probe_summary", None), seed.probe_summary) if row else seed.probe_summary,
                visibility=_row_text(getattr(row, "visibility", None), seed.visibility) if row else seed.visibility,
                **_promotion_readiness_fields(seed.key, performance_map.get(seed.key)),
            )
            if item.visibility == "hidden" and not can_view_hidden:
                continue
            if item.visibility == "backtest_only" and not can_view_backtest_only:
                continue
            if item.category_key == "factor" and not can_view_factor:
                continue
            items.append(item)
        items.sort(key=lambda item: (item.sort_order, item.key))
        return StrategyMetaResponse(strategies=items)

    def list_presets(self) -> StrategyPresetResponse:
        rows = self._load_preset_rows()
        production_keys = self._current_production_strategy_keys()
        if not rows:
            return StrategyPresetResponse(
                presets=[_preset_from_seed(item, production_keys=production_keys) for item in DEFAULT_PRESETS]
            )
        return StrategyPresetResponse(
            presets=[_filter_preset(_preset_from_row(row), production_keys=production_keys) for row in rows]
        )

    def validate_backtest_strategy_access(
        self,
        strategy_keys: list[str],
        *,
        current_user: User | None,
    ) -> None:
        """Validate direct backtest access against the same strategy metadata source.

        UI visibility is not treated as permission.  Direct API calls must pass
        this gate so hidden/factor/backtest-only strategies cannot be triggered
        by ordinary users just by sending a raw strategy key.
        """

        roles = _roles(current_user)
        is_admin = _has_any_role(roles, ADMIN_ROLES)
        can_use_factor = _has_any_role(roles, FACTOR_ACCESS_ROLES)
        can_use_research = _has_any_role(roles, RESEARCH_ACCESS_ROLES)
        overrides = self._load_metadata_overrides()
        resolver = self._tier_resolver()
        seen: set[str] = set()
        for raw_key in strategy_keys:
            strategy_key = str(raw_key or "").strip()
            if not strategy_key or strategy_key in seen:
                continue
            seen.add(strategy_key)
            seed = DEFAULT_STRATEGY_SEEDS_BY_KEY.get(strategy_key)
            row = overrides.get(strategy_key)
            if seed is None and row is None:
                raise ValueError(f"未知策略：{strategy_key}")
            tier = resolver.resolve(strategy_key, fallback=_metadata_fallback_tier(seed, row))
            visibility = _row_text(
                getattr(row, "visibility", None) if row is not None else None,
                seed.visibility if seed is not None else "full",
            )
            probe_status = _row_text(
                getattr(row, "probe_status", None) if row is not None else None,
                seed.probe_status if seed is not None else "not_required",
            )
            enabled = _row_bool(
                getattr(row, "enabled", None) if row is not None else None,
                seed.enabled if seed is not None else True,
            )
            if probe_status == "failed":
                raise ValueError(f"策略探针失败，暂不允许回测：{strategy_key}")
            if visibility == "hidden" and not is_admin:
                raise PermissionError(f"策略不可见：{strategy_key}")
            if visibility == "backtest_only" and not can_use_research:
                raise PermissionError(f"策略仅限研究回测权限使用：{strategy_key}")
            if tier == StrategyTier.FACTOR and not can_use_factor:
                raise PermissionError(f"策略因子仅限研究/优化权限使用：{strategy_key}")
            if not enabled or not _strategy_feature_enabled(self.db, strategy_key, default=enabled):
                raise ValueError(f"策略已禁用：{strategy_key}")

    def promote_strategy(
        self,
        payload: StrategyGovernanceMutationRequest,
        *,
        current_user: User,
    ) -> StrategyGovernanceMutationResponse:
        strategy_key = payload.strategy_key.strip()
        target_tier = _normalize_tier(payload.target_tier)
        if target_tier not in {"core", "auxiliary", "research", "factor"}:
            raise ValueError("target_tier 必须是 core/auxiliary/research/factor")
        metadata = self._load_metadata_overrides().get(strategy_key)
        seed = DEFAULT_STRATEGY_SEEDS_BY_KEY.get(strategy_key)
        if seed is None and metadata is None:
            raise ValueError(f"未知策略：{strategy_key}")
        if target_tier in {"core", "auxiliary"}:
            probe_status = _row_text(
                getattr(metadata, "probe_status", None) if metadata is not None else None,
                seed.probe_status if seed is not None else "not_required",
            )
            visibility = _row_text(
                getattr(metadata, "visibility", None) if metadata is not None else None,
                seed.visibility if seed is not None else "full",
            )
            enabled = _row_bool(
                getattr(metadata, "enabled", None) if metadata is not None else None,
                seed.enabled if seed is not None else True,
            )
            if probe_status not in {"not_required", "passed"}:
                raise ValueError(f"策略探针状态为 {probe_status}，暂不允许提升到生产层")
            if visibility != "full":
                raise ValueError(f"策略可见性为 {visibility}，暂不允许提升到生产层")
            if not enabled or not _strategy_feature_enabled(self.db, strategy_key, default=enabled):
                raise ValueError("策略当前已禁用，暂不允许提升到生产层")
            if strategy_key in RESEARCH_TO_AUXILIARY_GATED_STRATEGIES:
                performance = latest_strategy_performance_map(self.db).get(strategy_key)
                health_score, _ = _strategy_health(performance)
                filled = int(getattr(performance, "filled_signals", 0) or 0)
                if filled < RESEARCH_TO_AUXILIARY_MIN_FILLED or health_score < RESEARCH_TO_AUXILIARY_MIN_HEALTH:
                    raise ValueError(
                        f"策略真实成交样本或健康度不足：成交 {filled}/{RESEARCH_TO_AUXILIARY_MIN_FILLED}，"
                        f"健康分 {health_score:.1f}/{RESEARCH_TO_AUXILIARY_MIN_HEALTH:.1f}"
                    )
        current_tier = self._tier_resolver().resolve(strategy_key).value
        row = self.db.execute(
            select(StrategyTierOverride).where(StrategyTierOverride.strategy_key == strategy_key)
        ).scalar_one_or_none()
        now = datetime.now()
        if row is None:
            row = StrategyTierOverride(strategy_key=strategy_key)
            self.db.add(row)
        row.override_tier = target_tier
        row.reason = payload.reason
        row.evidence_summary = payload.evidence_summary
        row.operator_user_id = current_user.id
        row.promoted_at = now
        row.reverted_at = None
        self.db.add(
            StrategyTierOverrideLog(
                strategy_key=strategy_key,
                action="promote",
                from_tier=current_tier,
                to_tier=target_tier,
                reason=payload.reason,
                evidence_summary=payload.evidence_summary,
                operator_user_id=current_user.id,
            )
        )
        self.db.commit()
        clear_strategy_tier_cache(strategy_key)
        return StrategyGovernanceMutationResponse(
            ok=True,
            strategy_key=strategy_key,
            action="promote",
            tier=target_tier,
            message="策略层级已更新",
        )

    def demote_strategy(
        self,
        payload: StrategyGovernanceMutationRequest,
        *,
        current_user: User,
    ) -> StrategyGovernanceMutationResponse:
        strategy_key = payload.strategy_key.strip()
        current_tier = self._tier_resolver().resolve(strategy_key).value
        row = self.db.execute(
            select(StrategyTierOverride).where(StrategyTierOverride.strategy_key == strategy_key)
        ).scalar_one_or_none()
        if row is None:
            row = StrategyTierOverride(strategy_key=strategy_key, override_tier=current_tier)
            self.db.add(row)
        row.reverted_at = datetime.now()
        row.reason = payload.reason
        row.evidence_summary = payload.evidence_summary
        row.operator_user_id = current_user.id
        self.db.add(
            StrategyTierOverrideLog(
                strategy_key=strategy_key,
                action="demote",
                from_tier=current_tier,
                to_tier=get_strategy_tier(strategy_key).value,
                reason=payload.reason,
                evidence_summary=payload.evidence_summary,
                operator_user_id=current_user.id,
            )
        )
        self.db.commit()
        clear_strategy_tier_cache(strategy_key)
        return StrategyGovernanceMutationResponse(
            ok=True,
            strategy_key=strategy_key,
            action="demote",
            tier=get_strategy_tier(strategy_key).value,
            message="策略层级覆盖已撤回",
        )

    def search_symbols(self, query: str, limit: int = 10) -> SymbolSearchResponse:
        keyword = query.strip()
        if not keyword:
            return SymbolSearchResponse(items=[], total=0)
        safe_limit = max(1, min(limit, 20))
        rows = self._search_instruments(keyword, safe_limit)
        total = self._count_instruments(keyword)
        fallback_symbols: list[str] = []
        if len(rows) < safe_limit:
            fallback_symbols = self._search_daily_bar_symbols(
                keyword=keyword,
                limit=safe_limit - len(rows),
                excluded={row.symbol for row in rows},
            )
            total += self._count_daily_bar_symbols(keyword, excluded={row.symbol for row in rows})
        prices = self._latest_prices([row.symbol for row in rows] + fallback_symbols)
        items = [
            SymbolSearchItem(
                symbol=row.symbol,
                name=row.name or "",
                latest_price=prices.get(row.symbol),
                industry=row.sector_name or "",
                market=row.market or "",
                instrument_type=row.instrument_type or "stock",
            )
            for row in rows
        ]
        items.extend(
            SymbolSearchItem(
                symbol=symbol,
                name=symbol,
                latest_price=prices.get(symbol),
                market="CN",
                instrument_type="stock",
            )
            for symbol in fallback_symbols
        )
        return SymbolSearchResponse(items=items, total=total)

    def _load_metadata_overrides(self) -> dict[str, StrategyMetadata]:
        if not hasattr(self.db, "execute"):
            return {}
        try:
            rows = self.db.execute(select(StrategyMetadata)).scalars().all()
        except (AttributeError, SQLAlchemyError):
            return {}
        return {row.key: row for row in rows}

    def _load_preset_rows(self) -> list[StrategyPreset]:
        if not hasattr(self.db, "execute"):
            return []
        try:
            return list(
                self.db.execute(select(StrategyPreset).order_by(StrategyPreset.sort_order.asc(), StrategyPreset.id.asc()))
                .scalars()
                .all()
            )
        except (AttributeError, SQLAlchemyError):
            return []

    def _current_production_strategy_keys(self) -> list[str]:
        return [
            item.key
            for item in self.list_strategy_meta().strategies
            if item.enabled and item.visibility == "full" and item.category_key in {"core", "auxiliary"}
        ]

    def _tier_resolver(self) -> StrategyTierResolver:
        return StrategyTierResolver(self.db if hasattr(self.db, "execute") else None)

    def _search_instruments(self, keyword: str, limit: int) -> list[Instrument]:
        escaped = _escape_like(keyword)
        pattern = f"%{escaped}%"
        prefix = f"{escaped}%"
        statement = (
            select(Instrument)
            .where(
                or_(
                    Instrument.symbol.like(prefix, escape="\\"),
                    Instrument.name.like(pattern, escape="\\"),
                    Instrument.sector_name.like(pattern, escape="\\"),
                )
            )
            .order_by(Instrument.instrument_type.asc(), Instrument.symbol.asc())
            .limit(limit)
        )
        return list(self.db.execute(statement).scalars().all())

    def _count_instruments(self, keyword: str) -> int:
        escaped = _escape_like(keyword)
        pattern = f"%{escaped}%"
        prefix = f"{escaped}%"
        statement = select(func.count(Instrument.id)).where(
            or_(
                Instrument.symbol.like(prefix, escape="\\"),
                Instrument.name.like(pattern, escape="\\"),
                Instrument.sector_name.like(pattern, escape="\\"),
            )
        )
        return int(self.db.execute(statement).scalar() or 0)

    def _search_daily_bar_symbols(self, keyword: str, limit: int, excluded: set[str]) -> list[str]:
        latest_date = self.db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar()
        if not latest_date:
            return []
        prefix = f"{_escape_like(keyword)}%"
        statement = (
            select(distinct(DailyBarSnapshot.symbol))
            .where(
                DailyBarSnapshot.trade_date == latest_date,
                DailyBarSnapshot.symbol.like(prefix, escape="\\"),
            )
            .order_by(DailyBarSnapshot.symbol.asc())
            .limit(limit + len(excluded))
        )
        symbols = [str(row[0]) for row in self.db.execute(statement).all()]
        return [symbol for symbol in symbols if symbol not in excluded][:limit]

    def _count_daily_bar_symbols(self, keyword: str, excluded: set[str]) -> int:
        latest_date = self.db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar()
        if not latest_date:
            return 0
        prefix = f"{_escape_like(keyword)}%"
        statement = select(func.count(distinct(DailyBarSnapshot.symbol))).where(
            DailyBarSnapshot.trade_date == latest_date,
            DailyBarSnapshot.symbol.like(prefix, escape="\\"),
        )
        if excluded:
            statement = statement.where(DailyBarSnapshot.symbol.notin_(excluded))
        return int(self.db.execute(statement).scalar() or 0)

    def _latest_prices(self, symbols: list[str]) -> dict[str, float]:
        if not symbols:
            return {}
        latest_date = self.db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar()
        if not latest_date:
            return {}
        rows = self.db.execute(
            select(DailyBarSnapshot.symbol, DailyBarSnapshot.close_price).where(
                DailyBarSnapshot.trade_date == latest_date,
                DailyBarSnapshot.symbol.in_(symbols),
            )
        ).all()
        return {str(symbol): float(price or 0) for symbol, price in rows}
