from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EtfCategory(str, Enum):
    BROAD_BASE = "broad_base"
    SECTOR = "sector"
    CROSS_BORDER = "cross_border"
    BOND = "bond"
    GOLD = "gold"
    MONEY = "money"
    COMMODITY = "commodity"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EtfProfile:
    symbol: str
    name: str
    category: EtfCategory
    t0_eligible: bool
    settlement_rule: str
    tracking_index: str = ""
    min_amount: float = 0.0
    max_spread_bps: float = 0.0
    slippage_bps: float = 0.0
    premium_discount_available: bool = False
    enabled_for_t0: bool = True
    notes: str = ""

    @property
    def same_day_sell_allowed(self) -> bool:
        return self.t0_eligible and self.enabled_for_t0 and self.settlement_rule == "t0"


ETF_UNIVERSE_VERSION = "etf-universe-v1"
ETF_PREFIXES = ("15", "16", "50", "51", "56", "58")

T0_KEYWORDS = tuple(
    dict.fromkeys(
        (
            "货币",
            "黄金",
            "国债",
            "债券",
            "政金债",
            "信用债",
            "可转债",
            "跨境",
            "纳指",
            "纳斯达克",
            "恒生",
            "日经",
            "标普",
            "德国",
            "法国",
            "印度",
            "沙特",
            "港股",
            "美股",
            "海外",
            "东南亚",
            "日本",
            "全球",
        )
    )
)

_DEFAULT_MIN_AMOUNT = 50_000_000.0
_BROAD_BASE_MIN_AMOUNT = 100_000_000.0
_T0_MIN_AMOUNT = 30_000_000.0


_ETF_UNIVERSE: dict[str, EtfProfile] = {
    "510300": EtfProfile("510300", "沪深300ETF", EtfCategory.BROAD_BASE, True, "t0", "沪深300", _BROAD_BASE_MIN_AMOUNT, 8, 4, False, notes="宽基 ETF，保留既有模拟盘 T+0 行为。"),
    "510500": EtfProfile("510500", "中证500ETF", EtfCategory.BROAD_BASE, True, "t0", "中证500", _BROAD_BASE_MIN_AMOUNT, 8, 4, False, notes="宽基 ETF，保留既有模拟盘 T+0 行为。"),
    "159915": EtfProfile("159915", "创业板ETF", EtfCategory.BROAD_BASE, True, "t0", "创业板指", _BROAD_BASE_MIN_AMOUNT, 8, 4, False, notes="宽基 ETF，保留既有模拟盘 T+0 行为。"),
    "588000": EtfProfile("588000", "科创50ETF", EtfCategory.BROAD_BASE, True, "t0", "科创50", _BROAD_BASE_MIN_AMOUNT, 10, 5, False, notes="宽基 ETF，保留既有模拟盘 T+0 行为。"),
    "510310": EtfProfile("510310", "消费ETF", EtfCategory.SECTOR, True, "t0", "消费", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "512170": EtfProfile("512170", "医疗ETF", EtfCategory.SECTOR, True, "t0", "医疗", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "512200": EtfProfile("512200", "房地产ETF", EtfCategory.SECTOR, True, "t0", "房地产", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "512400": EtfProfile("512400", "有色金属ETF", EtfCategory.SECTOR, True, "t0", "有色金属", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "512480": EtfProfile("512480", "半导体ETF", EtfCategory.SECTOR, True, "t0", "半导体", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF，需在执行前继续检查流动性和价差。"),
    "512660": EtfProfile("512660", "军工ETF", EtfCategory.SECTOR, True, "t0", "国防军工", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "512690": EtfProfile("512690", "酒ETF", EtfCategory.SECTOR, True, "t0", "白酒", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "512760": EtfProfile("512760", "芯片ETF", EtfCategory.SECTOR, True, "t0", "芯片", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "512800": EtfProfile("512800", "银行ETF", EtfCategory.SECTOR, True, "t0", "银行", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF，需在执行前继续检查流动性和价差。"),
    "512880": EtfProfile("512880", "证券ETF", EtfCategory.SECTOR, True, "t0", "证券公司", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF，需在执行前继续检查流动性和价差。"),
    "515000": EtfProfile("515000", "科技ETF", EtfCategory.SECTOR, True, "t0", "科技", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "515220": EtfProfile("515220", "煤炭ETF", EtfCategory.SECTOR, True, "t0", "煤炭", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "515790": EtfProfile("515790", "光伏ETF", EtfCategory.SECTOR, True, "t0", "光伏", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "516780": EtfProfile("516780", "稀土ETF", EtfCategory.SECTOR, True, "t0", "稀土", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "159930": EtfProfile("159930", "能源ETF", EtfCategory.SECTOR, True, "t0", "能源", _DEFAULT_MIN_AMOUNT, 12, 5, False, notes="行业 ETF 白名单，需在执行前继续检查流动性和价差。"),
    "511880": EtfProfile("511880", "银华日利", EtfCategory.MONEY, True, "t0", "货币基金", _T0_MIN_AMOUNT, 5, 2, False, notes="货币 ETF，T+0 能力明确但收益空间通常很低。"),
    "518880": EtfProfile("518880", "黄金ETF", EtfCategory.GOLD, True, "t0", "黄金现货", _T0_MIN_AMOUNT, 10, 4, True, notes="黄金 ETF，需关注商品联动和折溢价。"),
    "513100": EtfProfile("513100", "纳指ETF", EtfCategory.CROSS_BORDER, True, "t0", "纳斯达克100", _T0_MIN_AMOUNT, 18, 8, True, notes="跨境 ETF，需关注时差、溢价和汇率扰动。"),
}


def normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def is_known_etf(symbol: str, name: str = "", instrument_type: str = "") -> bool:
    symbol_value = normalize_symbol(symbol)
    type_value = str(instrument_type or "").strip().lower()
    if type_value in {"etf", "fund", "lof", "index_fund", "money_fund"}:
        return True
    if symbol_value in _ETF_UNIVERSE:
        return True
    return symbol_value.startswith(ETF_PREFIXES) or "ETF" in str(name or "").upper()


def list_etf_profiles(params: dict[str, Any] | None = None) -> list[EtfProfile]:
    return sorted(_profile_universe(params).values(), key=lambda item: item.symbol)


def etf_profile_for(
    symbol: str,
    name: str = "",
    instrument_type: str = "",
    params: dict[str, Any] | None = None,
) -> EtfProfile | None:
    symbol_value = normalize_symbol(symbol)
    if not is_known_etf(symbol_value, name=name, instrument_type=instrument_type):
        return None
    profile = _profile_universe(params).get(symbol_value)
    if profile is not None:
        return profile
    category = etf_category_for(symbol_value, name=name)
    t0_eligible = _infer_t0_eligible(symbol_value, name=name, category=category)
    return EtfProfile(
        symbol=symbol_value,
        name=str(name or symbol_value),
        category=category,
        t0_eligible=t0_eligible,
        settlement_rule="t0" if t0_eligible else "t1",
        min_amount=_T0_MIN_AMOUNT if t0_eligible else _DEFAULT_MIN_AMOUNT,
        max_spread_bps=18 if t0_eligible else 12,
        slippage_bps=8 if category == EtfCategory.CROSS_BORDER else 5,
        premium_discount_available=category in {EtfCategory.CROSS_BORDER, EtfCategory.GOLD, EtfCategory.COMMODITY},
        enabled_for_t0=t0_eligible,
        notes="按名称/代码推断，生产执行前必须补齐流动性、价差和数据质量检查。",
    )


def etf_category_for(symbol: str, name: str = "") -> EtfCategory:
    text = f"{normalize_symbol(symbol)} {name or ''}".upper()
    chinese = str(name or "")
    if any(keyword in chinese for keyword in ("货币", "添富快线", "银华日利")) or normalize_symbol(symbol).startswith("511"):
        return EtfCategory.MONEY
    if "黄金" in chinese or normalize_symbol(symbol).startswith("518"):
        return EtfCategory.GOLD
    if any(keyword in chinese for keyword in ("债", "国债", "政金债", "信用债", "可转债")):
        return EtfCategory.BOND
    if any(keyword in chinese for keyword in ("纳指", "纳斯达克", "恒生", "标普", "日经", "德国", "法国", "印度", "沙特", "港股", "美股", "海外")):
        return EtfCategory.CROSS_BORDER
    if any(keyword in chinese for keyword in ("商品", "豆粕", "能源化工", "有色", "原油")):
        return EtfCategory.COMMODITY
    if any(keyword in chinese for keyword in ("沪深300", "中证500", "中证1000", "创业板", "科创50", "上证50", "宽基")):
        return EtfCategory.BROAD_BASE
    if "ETF" in text or normalize_symbol(symbol).startswith(ETF_PREFIXES):
        return EtfCategory.SECTOR
    return EtfCategory.UNKNOWN


def is_t0_eligible_etf(symbol: str, name: str = "", instrument_type: str = "") -> bool:
    profile = etf_profile_for(symbol, name=name, instrument_type=instrument_type)
    return bool(profile and profile.same_day_sell_allowed)


def same_day_sell_allowed(symbol: str, name: str = "", instrument_type: str = "") -> bool:
    return is_t0_eligible_etf(symbol, name=name, instrument_type=instrument_type)


def _infer_t0_eligible(symbol: str, *, name: str, category: EtfCategory) -> bool:
    if category in {EtfCategory.MONEY, EtfCategory.GOLD, EtfCategory.BOND, EtfCategory.CROSS_BORDER, EtfCategory.COMMODITY}:
        return True
    if any(keyword in str(name or "") for keyword in T0_KEYWORDS):
        return True
    # Unknown stock/industry ETF must not be promoted to T+0 automatically.
    return False


def _profile_universe(params: dict[str, Any] | None = None) -> dict[str, EtfProfile]:
    result = dict(_ETF_UNIVERSE)
    values = params if params is not None else _runtime_sector_etf_params()
    overrides = values.get("universe_overrides") if isinstance(values, dict) else None
    if isinstance(overrides, dict):
        for symbol, raw in overrides.items():
            if not isinstance(raw, dict):
                continue
            profile = _profile_from_override(str(symbol), raw, fallback=result.get(normalize_symbol(str(symbol))))
            if profile is not None:
                result[profile.symbol] = profile
    return result


def _profile_from_override(symbol: str, raw: dict[str, Any], *, fallback: EtfProfile | None = None) -> EtfProfile | None:
    symbol_value = normalize_symbol(str(raw.get("symbol") or symbol))
    if not symbol_value:
        return None
    name = str(raw.get("name") or (fallback.name if fallback else symbol_value))
    category = _coerce_category(raw.get("category"), fallback.category if fallback else etf_category_for(symbol_value, name=name))
    t0_eligible = _bool_value(raw.get("t0_eligible"), fallback.t0_eligible if fallback else _infer_t0_eligible(symbol_value, name=name, category=category))
    settlement_rule = str(raw.get("settlement_rule") or (fallback.settlement_rule if fallback else ("t0" if t0_eligible else "t1"))).lower()
    enabled_for_t0 = _bool_value(raw.get("enabled_for_t0"), fallback.enabled_for_t0 if fallback else t0_eligible)
    return EtfProfile(
        symbol=symbol_value,
        name=name,
        category=category,
        t0_eligible=t0_eligible,
        settlement_rule=settlement_rule,
        tracking_index=str(raw.get("tracking_index") or (fallback.tracking_index if fallback else "")),
        min_amount=_float_value(raw.get("min_amount"), fallback.min_amount if fallback else (_T0_MIN_AMOUNT if t0_eligible else _DEFAULT_MIN_AMOUNT)),
        max_spread_bps=_float_value(raw.get("max_spread_bps"), fallback.max_spread_bps if fallback else (18.0 if t0_eligible else 12.0)),
        slippage_bps=_float_value(raw.get("slippage_bps"), fallback.slippage_bps if fallback else (8.0 if category == EtfCategory.CROSS_BORDER else 5.0)),
        premium_discount_available=_bool_value(
            raw.get("premium_discount_available"),
            fallback.premium_discount_available if fallback else category in {EtfCategory.CROSS_BORDER, EtfCategory.GOLD, EtfCategory.COMMODITY},
        ),
        enabled_for_t0=enabled_for_t0,
        notes=str(raw.get("notes") or (fallback.notes if fallback else "来自运行时 ETF universe 覆盖；生产执行仍需流动性、价差和数据质量检查。")),
    )


def _runtime_sector_etf_params() -> dict[str, Any]:
    try:
        from app.services.quant.runtime_parameters import get_market_sector_etf_t0

        values = get_market_sector_etf_t0()
    except Exception:
        return {}
    return values if isinstance(values, dict) else {}


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
