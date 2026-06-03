from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timezone import beijing_now_string
from app.models.entities import Instrument, UserSectorExclusion


DEFAULT_A_SHARE_SECTORS: tuple[str, ...] = (
    "半导体",
    "人工智能",
    "机器人",
    "软件服务",
    "通信设备",
    "消费电子",
    "电子元件",
    "光伏设备",
    "电池",
    "新能源汽车",
    "汽车零部件",
    "电力设备",
    "储能",
    "军工",
    "航天航空",
    "船舶制造",
    "证券",
    "银行",
    "保险",
    "房地产",
    "建筑工程",
    "工程机械",
    "钢铁",
    "煤炭",
    "有色金属",
    "化工",
    "医药",
    "医疗器械",
    "白酒",
    "食品饮料",
    "家电",
    "传媒",
    "游戏",
    "旅游酒店",
    "电力",
    "燃气",
    "环保",
    "农业",
    "养殖",
    "物流",
    "港口航运",
    "纺织服装",
)

_SECTOR_FIELD_KEYS = (
    "sector_name",
    "industry",
    "industry_name",
    "sector",
    "board_name",
    "mainline_sector",
)
_FILTER_CACHE_TTL_SECONDS = 30.0
_FILTER_CACHE_LOCK = threading.RLock()
_PRIORITY_FILTER_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class UserSectorPreferenceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_available_sectors(self) -> list[str]:
        rows = (
            self.db.execute(
                select(Instrument.sector_name)
                .where(Instrument.sector_name.is_not(None))
                .where(func.length(func.trim(Instrument.sector_name)) > 0)
                .distinct()
                .order_by(Instrument.sector_name.asc())
            )
            .scalars()
            .all()
        )
        names = {_normalize_sector_name(row) for row in rows}
        names.update(DEFAULT_A_SHARE_SECTORS)
        return sorted(name for name in names if name)

    def get_excluded_sectors(self, user_id: int) -> list[str]:
        rows = (
            self.db.execute(
                select(UserSectorExclusion.sector_name)
                .where(UserSectorExclusion.user_id == user_id)
                .order_by(UserSectorExclusion.sector_name.asc())
            )
            .scalars()
            .all()
        )
        return sorted({_normalize_sector_name(row) for row in rows if _normalize_sector_name(row)})

    def get_excluded_sector_set(self, user_id: int) -> set[str]:
        return set(self.get_excluded_sectors(user_id))

    def replace_excluded_sectors(self, user_id: int, sectors: Iterable[str]) -> list[str]:
        normalized = sorted({_normalize_sector_name(item) for item in sectors if _normalize_sector_name(item)})
        if len(normalized) > 300:
            raise ValueError("板块排除数量不能超过 300 个")
        self.db.execute(delete(UserSectorExclusion).where(UserSectorExclusion.user_id == user_id))
        now = datetime.utcnow()
        for sector in normalized:
            self.db.add(
                UserSectorExclusion(
                    user_id=user_id,
                    sector_name=sector,
                    created_at=now,
                    updated_at=now,
                )
            )
        self.db.commit()
        invalidate_priority_board_filter_cache(user_id)
        return normalized

    def build_response(self, user_id: int) -> dict[str, Any]:
        excluded = self.get_excluded_sectors(user_id)
        return {
            "available_sectors": self.list_available_sectors(),
            "excluded_sectors": excluded,
            "excluded_count": len(excluded),
            "updated_at": beijing_now_string(),
        }


def filter_low_buy_screener_response(response: Any, excluded_sectors: set[str]) -> Any:
    if not excluded_sectors:
        return response
    payload = _model_payload(response)
    payload["candidates"] = _filter_items(payload.get("candidates"), excluded_sectors)
    payload["confirmed_candidates"] = _filter_items(payload.get("confirmed_candidates"), excluded_sectors)
    payload["matched_count"] = len(payload.get("candidates") or [])
    payload["history_sections"] = [
        {**section, "candidates": _filter_items(section.get("candidates"), excluded_sectors)}
        for section in payload.get("history_sections", []) or []
    ]
    return _rebuild_model(response, payload)


def filter_low_buy_history_response(response: Any, excluded_sectors: set[str]) -> Any:
    if not excluded_sectors:
        return response
    payload = _model_payload(response)
    payload["history_sections"] = [
        {**section, "candidates": _filter_items(section.get("candidates"), excluded_sectors)}
        for section in payload.get("history_sections", []) or []
    ]
    return _rebuild_model(response, payload)


def filter_priority_board_response(response: Any, excluded_sectors: set[str]) -> Any:
    if not excluded_sectors:
        return response
    payload = _model_payload(response)
    filtered_items = _filter_items(payload.get("items"), excluded_sectors)
    payload["items"] = filtered_items
    payload["total_candidates"] = len(filtered_items)
    payload["immediate_count"], payload["focus_count"], payload["track_count"] = _priority_counts(filtered_items)
    payload["family_sections"] = _filter_family_sections(payload.get("family_sections"), excluded_sectors)
    payload["simple_buckets"] = _rebuild_simple_buckets(payload.get("simple_buckets"), filtered_items)
    return _rebuild_model(response, payload)


def filter_priority_board_response_for_user(response: Any, *, user_id: int, excluded_sectors: set[str]) -> Any:
    if not excluded_sectors:
        return response
    if not getattr(get_settings(), "priority_board_filter_cache_enabled", True):
        return filter_priority_board_response(response, excluded_sectors)
    cache_key = _priority_filter_cache_key(response, user_id=user_id, excluded_sectors=excluded_sectors)
    cached = _priority_filter_cache_get(cache_key)
    if cached is not None:
        return _rebuild_model(response, cached)
    filtered = filter_priority_board_response(response, excluded_sectors)
    _priority_filter_cache_set(cache_key, _model_payload(filtered))
    return filtered


def invalidate_priority_board_filter_cache(user_id: int) -> None:
    prefix = f"user={int(user_id)}:"
    with _FILTER_CACHE_LOCK:
        for key in list(_PRIORITY_FILTER_CACHE):
            if key.startswith(prefix):
                _PRIORITY_FILTER_CACHE.pop(key, None)


def filter_monitor_snapshot_payload(payload: dict[str, Any], excluded_sectors: set[str]) -> dict[str, Any]:
    if not excluded_sectors:
        return payload
    next_payload = dict(payload)
    board = next_payload.get("priority_board")
    if isinstance(board, dict):
        next_payload["priority_board"] = filter_priority_board_payload(board, excluded_sectors)
    sector_etf = next_payload.get("sector_etf_t0")
    if isinstance(sector_etf, dict):
        opportunities = _filter_items(sector_etf.get("opportunities"), excluded_sectors)
        next_payload["sector_etf_t0"] = {
            **sector_etf,
            "opportunities": opportunities,
            "total": len(opportunities),
        }
    return next_payload


def filter_priority_board_payload(payload: dict[str, Any], excluded_sectors: set[str]) -> dict[str, Any]:
    if not excluded_sectors:
        return payload
    filtered_items = _filter_items(payload.get("items"), excluded_sectors)
    immediate, focus, track = _priority_counts(filtered_items)
    return {
        **payload,
        "items": filtered_items,
        "total_candidates": len(filtered_items),
        "immediate_count": immediate,
        "focus_count": focus,
        "track_count": track,
        "family_sections": _filter_family_sections(payload.get("family_sections"), excluded_sectors),
        "simple_buckets": _rebuild_simple_buckets(payload.get("simple_buckets"), filtered_items),
    }


def candidate_matches_excluded_sector(candidate: Any, excluded_sectors: set[str]) -> bool:
    if not excluded_sectors:
        return False
    names = _candidate_sector_names(candidate)
    return any(_sector_matches(name, excluded_sectors) for name in names)


def _filter_items(items: Any, excluded_sectors: set[str]) -> list[Any]:
    if not isinstance(items, list):
        return []
    return [item for item in items if not candidate_matches_excluded_sector(item, excluded_sectors)]


def _filter_family_sections(sections: Any, excluded_sectors: set[str]) -> list[dict[str, Any]]:
    if not isinstance(sections, list):
        return []
    result: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            section = _model_payload(section)
        items = _filter_items(section.get("items"), excluded_sectors)
        immediate, focus, track = _priority_counts(items)
        avg_score = round(sum(_float_value(item, "priority_score") for item in items) / max(len(items), 1), 2) if items else 0.0
        result.append({
            **section,
            "items": items,
            "total_candidates": len(items),
            "immediate_count": immediate,
            "focus_count": focus,
            "track_count": track,
            "avg_priority_score": avg_score,
        })
    return result


def _rebuild_simple_buckets(buckets: Any, items: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(buckets, list):
        return []
    by_key: dict[str, list[Any]] = {}
    for item in items:
        key = str(_field(item, "simple_bucket") or "give_up")
        by_key.setdefault(key, []).append(item)
    result: list[dict[str, Any]] = []
    for bucket in buckets:
        if not isinstance(bucket, dict):
            bucket = _model_payload(bucket)
        key = str(bucket.get("key") or "")
        bucket_items = by_key.get(key, [])
        result.append({
            **bucket,
            "count": len(bucket_items),
            "symbols": [str(_field(item, "symbol") or "") for item in bucket_items if _field(item, "symbol")],
        })
    return result


def _priority_counts(items: list[Any]) -> tuple[int, int, int]:
    immediate = sum(1 for item in items if str(_field(item, "simple_bucket") or "") == "buy_now")
    focus = sum(1 for item in items if str(_field(item, "simple_bucket") or "") == "wait_price")
    track = sum(1 for item in items if str(_field(item, "simple_bucket") or "") == "give_up")
    return immediate, focus, track


def _candidate_sector_names(candidate: Any) -> set[str]:
    names: set[str] = set()
    payload = _model_payload(candidate)
    for key in _SECTOR_FIELD_KEYS:
        value = payload.get(key)
        if isinstance(value, str):
            normalized = _normalize_sector_name(value)
            if normalized:
                names.add(normalized)
    return names


def _sector_matches(name: str, excluded_sectors: set[str]) -> bool:
    normalized = _normalize_sector_name(name)
    if not normalized:
        return False
    if normalized in excluded_sectors:
        return True
    return any(excluded and excluded in normalized for excluded in excluded_sectors)


def _normalize_sector_name(value: Any) -> str:
    text = str(value or "").strip()
    for prefix in ("板块：", "行业：", "所属板块："):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    if text.endswith("板块") and len(text) > 2:
        text = text[:-2].strip()
    return text


def _model_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {}


def _rebuild_model(original: Any, payload: dict[str, Any]) -> Any:
    if isinstance(original, dict):
        return payload
    if hasattr(original, "model_validate"):
        return original.__class__.model_validate(payload)
    return payload


def _field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _float_value(value: Any, key: str) -> float:
    try:
        return float(_field(value, key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _priority_filter_cache_key(response: Any, *, user_id: int, excluded_sectors: set[str]) -> str:
    excluded_hash = hashlib.sha256(
        json.dumps(sorted(excluded_sectors), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    payload_hash = hashlib.sha256(
        json.dumps(_model_payload(response), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"user={int(user_id)}:excluded={excluded_hash}:payload={payload_hash}"


def _priority_filter_cache_get(cache_key: str) -> dict[str, Any] | None:
    now = time.monotonic()
    with _FILTER_CACHE_LOCK:
        cached = _PRIORITY_FILTER_CACHE.get(cache_key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            _PRIORITY_FILTER_CACHE.pop(cache_key, None)
            return None
        return dict(payload)


def _priority_filter_cache_set(cache_key: str, payload: dict[str, Any]) -> None:
    with _FILTER_CACHE_LOCK:
        _PRIORITY_FILTER_CACHE[cache_key] = (time.monotonic() + _FILTER_CACHE_TTL_SECONDS, dict(payload))
