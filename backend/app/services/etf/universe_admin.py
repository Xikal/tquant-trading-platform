from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import QuantParameterSet, User
from app.models.schema_defs.phase4 import QuantParameterRollbackRequest, QuantParameterSetCreate
from app.services.etf.universe import ETF_UNIVERSE_VERSION, EtfCategory, EtfProfile, etf_category_for, list_etf_profiles, normalize_symbol
from app.services.operation_audit import record_operation_audit
from app.services.quant.parameter_version_service import QuantParameterVersionService


ETF_UNIVERSE_AUDIT_SCOPE = "market.sector_etf_t0.universe_overrides"
ETF_UNIVERSE_QUANT_SCOPE = "low_buy"
_PROFILE_FIELDS = (
    "symbol",
    "name",
    "category",
    "t0_eligible",
    "settlement_rule",
    "tracking_index",
    "min_amount",
    "max_spread_bps",
    "slippage_bps",
    "premium_discount_available",
    "enabled_for_t0",
    "same_day_sell_allowed",
    "notes",
)
_HIGH_RISK_FIELDS = {"t0_eligible", "settlement_rule", "min_amount", "max_spread_bps", "enabled_for_t0"}


@dataclass(frozen=True)
class EtfUniverseValidationIssue:
    symbol: str
    severity: str
    field: str
    message: str
    suggested_value: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
            "suggested_value": self.suggested_value,
        }


@dataclass(frozen=True)
class EtfUniverseDiffItem:
    symbol: str
    field: str
    baseline_value: Any
    current_value: Any
    draft_value: Any
    risk_level: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "field": self.field,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "draft_value": self.draft_value,
            "risk_level": self.risk_level,
            "message": self.message,
        }


class EtfUniverseAdminService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.quant_service = QuantParameterVersionService(db)

    def admin_payload(self, draft_overrides: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        current_params = self._current_raw_params()
        current_overrides = _current_overrides(current_params)
        effective_overrides = normalize_overrides(draft_overrides) if draft_overrides is not None else current_overrides
        baseline_profiles = _profile_map({})
        current_profiles = _profile_map(current_overrides)
        draft_profiles = _profile_map(effective_overrides)
        validation = validate_overrides(effective_overrides)
        diff = build_diff(baseline_profiles, current_profiles, draft_profiles)
        issue_severity = _max_severity_by_symbol(validation)
        items = [
            {
                **_profile_to_dict(profile),
                "source": "override" if profile.symbol in effective_overrides else "baseline",
                "validation_severity": issue_severity.get(profile.symbol, "ok"),
            }
            for profile in sorted(draft_profiles.values(), key=lambda item: item.symbol)
        ]
        return {
            "version": ETF_UNIVERSE_VERSION,
            "updated_at": _now_string(),
            "audit_scope": ETF_UNIVERSE_AUDIT_SCOPE,
            "baseline_count": len(baseline_profiles),
            "current_count": len(current_profiles),
            "override_count": len(effective_overrides),
            "t0_enabled_count": sum(1 for item in draft_profiles.values() if item.same_day_sell_allowed),
            "items": items,
            "overrides": current_overrides,
            "normalized_overrides": effective_overrides,
            "validation": _validation_summary(validation),
            "diff": [item.to_dict() for item in diff],
            "recent_versions": self._recent_versions(),
            "notes": [
                "ETF universe 管理只维护品种能力与交易约束，不生成策略信号。",
                "策略决策仍由 Python 服务执行；Go 只读行情质量，Rust 只承载指标计算和 parity 验收。",
                "保存会写入量化参数审计和 operation audit，激活后运行时参数缓存会被清理。",
            ],
        }

    def repair_draft(self, *, symbol: str, name: str = "", category: str = "") -> dict[str, Any]:
        symbol_value = normalize_symbol(symbol)
        category_value = _coerce_category(category, etf_category_for(symbol_value, name=name))
        t0_eligible = category_value in {EtfCategory.MONEY, EtfCategory.GOLD, EtfCategory.BOND, EtfCategory.CROSS_BORDER, EtfCategory.COMMODITY}
        profile = EtfProfile(
            symbol=symbol_value,
            name=name or symbol_value,
            category=category_value,
            t0_eligible=t0_eligible,
            settlement_rule="t0" if t0_eligible else "t1",
            tracking_index=name or symbol_value,
            min_amount=30_000_000.0 if t0_eligible else 50_000_000.0,
            max_spread_bps=18.0 if t0_eligible else 12.0,
            slippage_bps=8.0 if category_value == EtfCategory.CROSS_BORDER else 5.0,
            premium_discount_available=category_value in {EtfCategory.CROSS_BORDER, EtfCategory.GOLD, EtfCategory.COMMODITY},
            enabled_for_t0=t0_eligible,
            notes="由 ETF universe 修复向导生成；激活前必须核对交易所规则、流动性、价差和数据质量。",
        )
        draft = {symbol_value: _profile_to_override(profile)}
        issues = validate_overrides(draft)
        high_risk = any(item.severity == "error" or item.field in _HIGH_RISK_FIELDS for item in issues)
        return {
            "draft_overrides": draft,
            "validation": _validation_summary(issues),
            "requires_confirmation": high_risk or t0_eligible,
            "notes": [
                "修复向导不写数据库，只生成可审计草稿。",
                "未知行业 ETF 默认不自动提升为 T+0；如需 T+0 必须显式填写规则和备注。",
            ],
        }

    def apply(
        self,
        *,
        draft_overrides: dict[str, dict[str, Any]],
        version: str,
        description: str,
        activate: bool,
        confirm_high_risk: bool,
        user: User | None,
        operator_ip: str = "",
    ) -> dict[str, Any]:
        normalized = normalize_overrides(draft_overrides)
        issues = validate_overrides(normalized)
        if any(item.severity == "error" for item in issues):
            raise ValueError("ETF universe 草稿存在 error，不能保存或激活。")
        current_params = self.quant_service.current(scope=ETF_UNIVERSE_QUANT_SCOPE).params
        diff = build_diff(_profile_map({}), _profile_map(_current_overrides(current_params)), _profile_map(normalized))
        if activate and any(item.risk_level == "high" for item in diff) and not confirm_high_risk:
            raise ValueError("ETF universe 存在高风险变更，必须二次确认。")
        params = self._current_raw_params()
        params.setdefault("market", {}).setdefault("sector_etf_t0", {})["universe_overrides"] = normalized
        created = self.quant_service.create(
            QuantParameterSetCreate(
                version=version,
                name="ETF Universe 管理变更",
                scope=ETF_UNIVERSE_QUANT_SCOPE,
                params=params,
                description=description,
                activate=activate,
            ),
            created_by=getattr(user, "username", None) or "admin",
        )
        record_operation_audit(
            self.db,
            operation="etf_universe_apply",
            user=user,
            resource_type="etf_universe",
            resource_id=created.version,
            operator_ip=operator_ip,
            detail={
                "activate": activate,
                "override_count": len(normalized),
                "error_count": sum(1 for item in issues if item.severity == "error"),
                "warning_count": sum(1 for item in issues if item.severity == "warning"),
                "high_risk_count": sum(1 for item in diff if item.risk_level == "high"),
            },
        )
        self.db.commit()
        return {
            "ok": True,
            "message": "ETF universe 已保存并激活。" if activate else "ETF universe 草稿已保存。",
            "version": created.version,
            "admin": self.admin_payload(),
        }

    def rollback(
        self,
        *,
        version: str,
        confirm: bool,
        user: User | None,
        operator_ip: str = "",
    ) -> dict[str, Any]:
        if not confirm:
            raise ValueError("回滚 ETF universe 必须显式确认。")
        rolled = self.quant_service.rollback(
            QuantParameterRollbackRequest(version=version, scope=ETF_UNIVERSE_QUANT_SCOPE),
            operator=getattr(user, "username", None) or "admin",
        )
        record_operation_audit(
            self.db,
            operation="etf_universe_rollback",
            user=user,
            resource_type="etf_universe",
            resource_id=rolled.version,
            operator_ip=operator_ip,
            detail={"version": version, "status": rolled.status},
        )
        self.db.commit()
        return {
            "ok": True,
            "message": f"ETF universe 已回滚到 {rolled.version}。",
            "version": rolled.version,
            "admin": self.admin_payload(),
        }

    def _recent_versions(self, limit: int = 12) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(QuantParameterSet)
            .where(QuantParameterSet.scope == ETF_UNIVERSE_QUANT_SCOPE)
            .order_by(QuantParameterSet.id.desc())
            .limit(limit)
        ).scalars().all()
        result: list[dict[str, Any]] = []
        for row in rows:
            params = _json_dict(getattr(row, "params_json", "{}"))
            overrides = _current_overrides(params)
            if not overrides and "ETF Universe" not in (row.name or "") and "ETF universe" not in (row.description or ""):
                continue
            result.append(
                {
                    "version": row.version,
                    "status": row.status,
                    "scope": row.scope,
                    "description": row.description or "",
                    "created_by": row.created_by or "",
                    "created_at": _dt_string(row.created_at),
                    "activated_at": _dt_string(row.activated_at),
                }
            )
        return result

    def _current_raw_params(self) -> dict[str, Any]:
        row = self.db.execute(
            select(QuantParameterSet)
            .where(QuantParameterSet.status == "active")
            .where(QuantParameterSet.scope == ETF_UNIVERSE_QUANT_SCOPE)
            .order_by(QuantParameterSet.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return {}
        return _json_dict(getattr(row, "params_json", "{}"))


def normalize_overrides(raw_overrides: dict[str, dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_overrides, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, raw in raw_overrides.items():
        if not isinstance(raw, dict):
            continue
        symbol = normalize_symbol(str(raw.get("symbol") or key))
        if not symbol:
            continue
        baseline = _profile_map({}).get(symbol)
        name = str(raw.get("name") or (baseline.name if baseline else symbol))
        category = _coerce_category(raw.get("category"), baseline.category if baseline else etf_category_for(symbol, name=name))
        t0_eligible = _bool_value(raw.get("t0_eligible"), baseline.t0_eligible if baseline else False)
        settlement_rule = str(raw.get("settlement_rule") or (baseline.settlement_rule if baseline else ("t0" if t0_eligible else "t1"))).strip().lower()
        enabled_for_t0 = _bool_value(raw.get("enabled_for_t0"), baseline.enabled_for_t0 if baseline else t0_eligible)
        override = {
            "symbol": symbol,
            "name": name,
            "category": category.value,
            "t0_eligible": t0_eligible,
            "settlement_rule": settlement_rule,
            "tracking_index": str(raw.get("tracking_index") or (baseline.tracking_index if baseline else "")),
            "min_amount": _float_value(raw.get("min_amount"), baseline.min_amount if baseline else (30_000_000.0 if t0_eligible else 50_000_000.0)),
            "max_spread_bps": _float_value(raw.get("max_spread_bps"), baseline.max_spread_bps if baseline else (18.0 if t0_eligible else 12.0)),
            "slippage_bps": _float_value(raw.get("slippage_bps"), baseline.slippage_bps if baseline else (8.0 if category == EtfCategory.CROSS_BORDER else 5.0)),
            "premium_discount_available": _bool_value(
                raw.get("premium_discount_available"),
                baseline.premium_discount_available if baseline else category in {EtfCategory.CROSS_BORDER, EtfCategory.GOLD, EtfCategory.COMMODITY},
            ),
            "enabled_for_t0": enabled_for_t0,
            "notes": str(raw.get("notes") or (baseline.notes if baseline else "")),
        }
        result[symbol] = override
    return dict(sorted(result.items()))


def validate_overrides(overrides: dict[str, dict[str, Any]] | None) -> list[EtfUniverseValidationIssue]:
    issues: list[EtfUniverseValidationIssue] = []
    seen: set[str] = set()
    normalized = normalize_overrides(overrides)
    for raw_key, raw in (overrides or {}).items():
        symbol = normalize_symbol(str(raw.get("symbol") if isinstance(raw, dict) else raw_key))
        if not symbol or len(symbol) > 16:
            issues.append(EtfUniverseValidationIssue(symbol=symbol, severity="error", field="symbol", message="symbol 必须非空且长度 1-16。"))
        if symbol in seen:
            issues.append(EtfUniverseValidationIssue(symbol=symbol, severity="error", field="symbol", message="symbol 重复。"))
        seen.add(symbol)
        if isinstance(raw, dict) and raw.get("category") not in (None, ""):
            try:
                EtfCategory(str(raw.get("category")))
            except ValueError:
                issues.append(EtfUniverseValidationIssue(symbol=symbol, severity="error", field="category", message="category 不属于 EtfCategory。"))
    for symbol, item in normalized.items():
        category = _coerce_category(item.get("category"), EtfCategory.UNKNOWN)
        t0_eligible = bool(item.get("t0_eligible"))
        settlement_rule = str(item.get("settlement_rule") or "").lower()
        enabled_for_t0 = bool(item.get("enabled_for_t0"))
        min_amount = _float_value(item.get("min_amount"), 0.0)
        max_spread = _float_value(item.get("max_spread_bps"), 0.0)
        slippage = _float_value(item.get("slippage_bps"), 0.0)
        notes = str(item.get("notes") or "")
        if t0_eligible and settlement_rule != "t0":
            issues.append(EtfUniverseValidationIssue(symbol, "error", "settlement_rule", "t0_eligible=true 时 settlement_rule 必须是 t0。", "t0"))
        if settlement_rule == "t0" and not enabled_for_t0:
            issues.append(EtfUniverseValidationIssue(symbol, "warning", "enabled_for_t0", "标的规则允许 T+0，但当前运营禁用。", True))
        if min_amount <= 0:
            issues.append(EtfUniverseValidationIssue(symbol, "error", "min_amount", "min_amount 必须大于 0。"))
        if max_spread <= 0 or max_spread > 50:
            issues.append(EtfUniverseValidationIssue(symbol, "warning", "max_spread_bps", "max_spread_bps 应在 0-50 bps 的可解释范围。"))
        if slippage < 0 or slippage > 30:
            issues.append(EtfUniverseValidationIssue(symbol, "warning", "slippage_bps", "slippage_bps 应在 0-30 bps 的可解释范围。"))
        if category in {EtfCategory.CROSS_BORDER, EtfCategory.GOLD, EtfCategory.COMMODITY} and not bool(item.get("premium_discount_available")):
            issues.append(EtfUniverseValidationIssue(symbol, "warning", "premium_discount_available", "跨境/黄金/商品 ETF 应标记折溢价数据可用性。", True))
        baseline = _profile_map({}).get(symbol)
        if baseline is None and category == EtfCategory.SECTOR and t0_eligible and not notes.strip():
            issues.append(EtfUniverseValidationIssue(symbol, "error", "notes", "未知行业 ETF 显式提升 T+0 必须填写交易规则、流动性和数据质量备注。"))
        elif baseline is None and t0_eligible and not notes.strip():
            issues.append(EtfUniverseValidationIssue(symbol, "warning", "notes", "新增 T+0 ETF 建议填写规则来源和运维备注。"))
    return issues


def build_diff(
    baseline_profiles: dict[str, EtfProfile],
    current_profiles: dict[str, EtfProfile],
    draft_profiles: dict[str, EtfProfile],
) -> list[EtfUniverseDiffItem]:
    symbols = sorted(set(baseline_profiles) | set(current_profiles) | set(draft_profiles))
    diff: list[EtfUniverseDiffItem] = []
    for symbol in symbols:
        baseline = _profile_to_dict(baseline_profiles.get(symbol))
        current = _profile_to_dict(current_profiles.get(symbol))
        draft = _profile_to_dict(draft_profiles.get(symbol))
        for field in _PROFILE_FIELDS:
            current_value = current.get(field)
            draft_value = draft.get(field)
            baseline_value = baseline.get(field)
            if current_value == draft_value:
                continue
            risk = _risk_level(field=field, baseline_value=baseline_value, current_value=current_value, draft_value=draft_value)
            diff.append(
                EtfUniverseDiffItem(
                    symbol=symbol,
                    field=field,
                    baseline_value=baseline_value,
                    current_value=current_value,
                    draft_value=draft_value,
                    risk_level=risk,
                    message=_diff_message(field, current_value, draft_value, risk),
                )
            )
    return diff


def _current_overrides(params: dict[str, Any]) -> dict[str, dict[str, Any]]:
    values = params.get("market", {}).get("sector_etf_t0", {}) if isinstance(params, dict) else {}
    overrides = values.get("universe_overrides") if isinstance(values, dict) else None
    return normalize_overrides(overrides if isinstance(overrides, dict) else {})


def _profile_map(overrides: dict[str, dict[str, Any]]) -> dict[str, EtfProfile]:
    return {item.symbol: item for item in list_etf_profiles(params={"universe_overrides": normalize_overrides(overrides)})}


def _profile_to_dict(profile: EtfProfile | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "symbol": profile.symbol,
        "name": profile.name,
        "category": profile.category.value,
        "t0_eligible": profile.t0_eligible,
        "settlement_rule": profile.settlement_rule,
        "tracking_index": profile.tracking_index,
        "min_amount": profile.min_amount,
        "max_spread_bps": profile.max_spread_bps,
        "slippage_bps": profile.slippage_bps,
        "premium_discount_available": profile.premium_discount_available,
        "enabled_for_t0": profile.enabled_for_t0,
        "same_day_sell_allowed": profile.same_day_sell_allowed,
        "notes": profile.notes,
    }


def _profile_to_override(profile: EtfProfile) -> dict[str, Any]:
    data = _profile_to_dict(profile)
    data.pop("same_day_sell_allowed", None)
    return data


def _validation_summary(issues: list[EtfUniverseValidationIssue]) -> dict[str, Any]:
    return {
        "error_count": sum(1 for item in issues if item.severity == "error"),
        "warning_count": sum(1 for item in issues if item.severity == "warning"),
        "info_count": sum(1 for item in issues if item.severity == "info"),
        "issues": [item.to_dict() for item in issues],
    }


def _max_severity_by_symbol(issues: list[EtfUniverseValidationIssue]) -> dict[str, str]:
    rank = {"ok": 0, "info": 1, "warning": 2, "error": 3}
    result: dict[str, str] = {}
    for issue in issues:
        current = result.get(issue.symbol, "ok")
        if rank.get(issue.severity, 0) > rank.get(current, 0):
            result[issue.symbol] = issue.severity
    return result


def _risk_level(*, field: str, baseline_value: Any, current_value: Any, draft_value: Any) -> str:
    if field == "t0_eligible" and current_value is False and draft_value is True:
        return "high"
    if field == "settlement_rule" and current_value != "t0" and draft_value == "t0":
        return "high"
    if field == "enabled_for_t0" and current_value is False and draft_value is True:
        return "high"
    if field == "min_amount":
        try:
            if float(draft_value or 0) < float(current_value or baseline_value or 0):
                return "high"
        except (TypeError, ValueError):
            return "medium"
    if field == "max_spread_bps":
        try:
            if float(draft_value or 0) > float(current_value or baseline_value or 0):
                return "medium"
        except (TypeError, ValueError):
            return "medium"
    if field in _HIGH_RISK_FIELDS:
        return "medium"
    return "low"


def _diff_message(field: str, current_value: Any, draft_value: Any, risk: str) -> str:
    prefix = "高风险变更" if risk == "high" else "变更"
    return f"{prefix}: {field} 从 {current_value!r} 调整为 {draft_value!r}"


def _coerce_category(value: Any, fallback: EtfCategory) -> EtfCategory:
    try:
        return EtfCategory(str(value or fallback.value))
    except ValueError:
        return fallback


def _float_value(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _bool_value(value: Any, fallback: bool) -> bool:
    if value is None:
        return bool(fallback)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return bool(fallback)


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        import json

        value = json.loads(raw or "{}")
    except Exception:
        return {}
    if not isinstance(value, dict):
        return {}
    return value


def _now_string() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _dt_string(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
