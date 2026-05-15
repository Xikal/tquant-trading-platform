from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.schemas import (
    AppBootstrapResponse,
    AppAndroidUpdateResponse,
    AppHomeResponse,
    AppInstrumentSearchResponse,
    AppLowBuyDetailResponse,
    AppLowBuyFavoriteRequest,
    AppLowBuyResponse,
    AppMutationResponse,
    AppPaperSummaryResponse,
    AppWatchlistDetailResponse,
    AppWatchlistResponse,
    AppWatchlistUpsertRequest,
    UserSectorExclusionsResponse,
    UserSectorExclusionsUpdate,
)
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY
from app.services.app_mobile import AppMobileService
from app.services.app_mobile.common import now_string
from app.services.app_mobile.update_manifest import (
    ANDROID_APK_PATH,
    android_apk_size,
    android_apk_sha256,
    load_android_update_manifest,
)
from app.services.market_data import DataSourceError
from app.services.user_sector_preferences import UserSectorPreferenceService

router = APIRouter(prefix="/app")
app_mobile_service = AppMobileService()


def _raise_not_found(exc: LookupError) -> None:
    raise HTTPException(status_code=404, detail=str(exc)) from exc


def _raise_low_buy_error(exc: Exception) -> None:
    if isinstance(exc, DataSourceError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=f"选股宝典接口失败: {exc}") from exc


@router.get("/bootstrap", response_model=AppBootstrapResponse)
def app_bootstrap():
    return app_mobile_service.bootstrap()


@router.get("/update/android", response_model=AppAndroidUpdateResponse)
def app_android_update(
    request: Request,
    current_version_code: int = Query(1, ge=1),
):
    manifest = load_android_update_manifest()
    latest_version_code = int(manifest.get("latest_version_code") or 1)
    min_supported_version_code = int(manifest.get("min_supported_version_code") or 1)
    mandatory = bool(manifest.get("mandatory") or current_version_code < min_supported_version_code)
    return AppAndroidUpdateResponse(
        current_version_code=current_version_code,
        latest_version_code=latest_version_code,
        latest_version_name=str(manifest.get("latest_version_name") or "1.0.0"),
        min_supported_version_code=min_supported_version_code,
        update_available=latest_version_code > current_version_code,
        mandatory=mandatory,
        title=str(manifest.get("title") or "发现新版本"),
        message=str(manifest.get("message") or "建议更新到最新版本。"),
        changelog=list(manifest.get("changelog") or []),
        apk_url=str(request.url_for("app_android_update_apk")),
        apk_size_bytes=android_apk_size(),
        apk_sha256=android_apk_sha256() or str(manifest.get("apk_sha256") or ""),
        published_at=str(manifest.get("published_at") or ""),
    )


@router.get("/update/android/apk", name="app_android_update_apk")
def app_android_update_apk():
    if not ANDROID_APK_PATH.exists():
        raise HTTPException(status_code=404, detail="安装包尚未发布")
    return FileResponse(
        ANDROID_APK_PATH,
        media_type="application/vnd.android.package-archive",
        filename="weis-quant-latest.apk",
    )


@router.get("/home", response_model=AppHomeResponse)
def app_home(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return app_mobile_service.home(db, user_id=current_user.id)


@router.get("/watchlist", response_model=AppWatchlistResponse)
def app_watchlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return app_mobile_service.list_watchlist(db, user_id=current_user.id)


@router.post("/watchlist", response_model=AppMutationResponse)
def app_watchlist_upsert(
    payload: AppWatchlistUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return app_mobile_service.upsert_watchlist(payload, db, user_id=current_user.id)


@router.get("/watchlist/{symbol}", response_model=AppWatchlistDetailResponse)
def app_watchlist_detail(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return app_mobile_service.get_watchlist_detail(symbol, db, user_id=current_user.id)
    except LookupError as exc:
        _raise_not_found(exc)


@router.delete("/watchlist/{symbol}", response_model=AppMutationResponse)
def app_watchlist_delete(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return app_mobile_service.delete_watchlist(symbol, db, user_id=current_user.id)
    except LookupError as exc:
        _raise_not_found(exc)


@router.get("/instruments/search", response_model=AppInstrumentSearchResponse)
def app_instrument_search(
    keyword: str = Query("", max_length=40),
    kind: Literal["all", "stock", "etf"] = Query("all"),
    page: int = Query(1, ge=1, le=20),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return app_mobile_service.search_instruments(
        db,
        keyword=keyword,
        kind=kind,
        page=page,
        page_size=page_size,
    )


@router.get("/low-buy", response_model=AppLowBuyResponse)
def app_low_buy(
    strategy: str = Query(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
    limit: int = Query(12, ge=1, le=40),
    scan_limit: int = Query(48, ge=12, le=480),
    scan_mode: Literal["quick", "full"] = Query("quick"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        kwargs = {
            "db": db,
            "strategy": strategy,
            "limit": limit,
            "scan_limit": scan_limit,
            "scan_mode": scan_mode,
            "user_id": current_user.id,
        }
        try:
            return app_mobile_service.low_buy(**kwargs)
        except TypeError as exc:
            if "user_id" not in str(exc) or "unexpected keyword" not in str(exc):
                raise
            kwargs.pop("user_id", None)
            return app_mobile_service.low_buy(**kwargs)
    except Exception as exc:
        _raise_low_buy_error(exc)


@router.get("/low-buy/{symbol}", response_model=AppLowBuyDetailResponse)
def app_low_buy_detail(
    symbol: str,
    strategy: str = Query(DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
    scan_limit: int = Query(72, ge=12, le=480),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return app_mobile_service.get_low_buy_detail(
            symbol=symbol,
            db=db,
            strategy=strategy,
            scan_limit=scan_limit,
            user_id=current_user.id,
        )
    except LookupError as exc:
        _raise_not_found(exc)
    except Exception as exc:
        _raise_low_buy_error(exc)


@router.post("/low-buy/{symbol}/favorite", response_model=AppMutationResponse)
def app_low_buy_favorite(
    symbol: str,
    payload: AppLowBuyFavoriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return app_mobile_service.favorite_low_buy(symbol, payload, db, user_id=current_user.id)


@router.get("/paper/summary", response_model=AppPaperSummaryResponse)
def app_paper_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = app_mobile_service.paper_summary(db, user_id=current_user.id)
    payload.update(
        {
            "updated_at": now_string(),
            "is_stale": False,
            "warnings": [],
        }
    )
    return payload


@router.get("/settings/sector-exclusions", response_model=UserSectorExclusionsResponse)
def app_sector_exclusions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return UserSectorPreferenceService(db).build_response(current_user.id)


@router.put("/settings/sector-exclusions", response_model=UserSectorExclusionsResponse)
def app_update_sector_exclusions(
    payload: UserSectorExclusionsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        UserSectorPreferenceService(db).replace_excluded_sectors(
            current_user.id,
            payload.excluded_sectors,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UserSectorPreferenceService(db).build_response(current_user.id)
