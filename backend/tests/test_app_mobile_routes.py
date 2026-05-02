from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import app_mobile
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.schemas import (
    AppBootstrapResponse,
    AppFeatureFlags,
    AppHomeResponse,
    AppHomeSummary,
    AppLowBuyDetailResponse,
    AppLowBuyFavoriteRequest,
    AppLowBuyPriorityBoard,
    AppLowBuyResponse,
    AppLowBuyStrategySummary,
    AppLowBuySummary,
    AppWatchlistResponse,
)
from app.services.market_data import DataSourceError


class _RouteServiceStub:
    def bootstrap(self):
        return AppBootstrapResponse(
            app_name="A股短线做T助手",
            app_version="1.0.0",
            min_supported_version="1.0.0",
            tabs=[],
            default_refresh_seconds=20,
            market_disclaimer="仅供研究",
            feature_flags=AppFeatureFlags(),
            updated_at="2026-04-22 10:00:00",
            is_stale=False,
            warnings=[],
        )

    def home(self, db, user_id=None):  # noqa: ARG002
        return AppHomeResponse(
            summary=AppHomeSummary(total=0),
            items=[],
            updated_at="2026-04-22 10:00:00",
            is_stale=False,
            warnings=[],
        )

    def list_watchlist(self, db, user_id=None):  # noqa: ARG002
        return AppWatchlistResponse(
            items=[],
            updated_at="2026-04-22 10:00:00",
            is_stale=False,
            warnings=[],
        )

    def upsert_watchlist(self, payload, db, user_id=None):  # noqa: ARG002
        return {"message": "自选股已保存", "symbol": payload.symbol}

    def get_watchlist_detail(self, symbol, db, user_id=None):  # noqa: ARG002
        raise LookupError(f"{symbol} not found")

    def delete_watchlist(self, symbol, db, user_id=None):  # noqa: ARG002
        raise LookupError(f"{symbol} not found")

    def low_buy(self, db, strategy, limit, scan_limit, scan_mode):  # noqa: ARG002
        if strategy == "raise-datasource":
            raise DataSourceError("数据源异常")
        if strategy == "raise-generic":
            raise RuntimeError("unknown")
        return AppLowBuyResponse(
            strategy=AppLowBuyStrategySummary(
                strategy_key="classic_retrace",
                strategy_title="原始低吸法",
            ),
            summary=AppLowBuySummary(
                as_of_date="2026-04-22",
                latest_trade_date="2026-04-22",
            ),
            priority_board=AppLowBuyPriorityBoard(),
            confirmed_candidates=[],
            watch_candidates=[],
            updated_at="2026-04-22 10:00:00",
            is_stale=False,
            warnings=[],
        )

    def get_low_buy_detail(self, symbol, db, strategy, scan_limit, user_id=None):  # noqa: ARG002
        if symbol == "404":
            raise LookupError("候选标的不存在")
        if symbol == "400":
            raise DataSourceError("数据源异常")
        if symbol == "500":
            raise RuntimeError("unknown")
        raise AssertionError("unexpected call")

    def favorite_low_buy(self, symbol, payload, db, user_id=None):  # noqa: ARG002
        return {"message": "已加入自选", "symbol": symbol, "memo": payload.memo}


class AppMobileRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_service = app_mobile.app_mobile_service
        app_mobile.app_mobile_service = _RouteServiceStub()

        self.app = FastAPI()
        self.app.include_router(app_mobile.router, prefix="/api")
        self.app.dependency_overrides[get_db] = lambda: iter([object()])
        self.app.dependency_overrides[get_current_user] = lambda: User(
            id=1,
            username="tester",
            display_name="tester",
            password_hash="x",
        )
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        app_mobile.app_mobile_service = self.original_service

    def test_bootstrap_endpoint(self) -> None:
        response = self.client.get("/api/app/bootstrap")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["app_name"], "A股短线做T助手")

    def test_watchlist_routes(self) -> None:
        response = self.client.get("/api/app/watchlist")
        self.assertEqual(response.status_code, 200)
        save = self.client.post(
            "/api/app/watchlist",
            json={
                "symbol": "510300",
                "name": "沪深300ETF",
                "base_position": 1000,
                "available_position": 1000,
                "cost_basis": None,
                "memo": "",
            },
        )
        self.assertEqual(save.status_code, 200)
        self.assertEqual(save.json()["symbol"], "510300")

    def test_watchlist_not_found_maps_to_404(self) -> None:
        detail = self.client.get("/api/app/watchlist/510300")
        delete = self.client.delete("/api/app/watchlist/510300")
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(delete.status_code, 404)

    def test_low_buy_error_mapping(self) -> None:
        ok = self.client.get("/api/app/low-buy")
        bad_source = self.client.get("/api/app/low-buy?strategy=raise-datasource")
        bad_generic = self.client.get("/api/app/low-buy?strategy=raise-generic")
        bad_mode = self.client.get("/api/app/low-buy?scan_mode=unexpected")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(bad_source.status_code, 400)
        self.assertEqual(bad_generic.status_code, 500)
        self.assertEqual(bad_mode.status_code, 422)

    def test_low_buy_detail_error_mapping(self) -> None:
        not_found = self.client.get("/api/app/low-buy/404")
        bad_source = self.client.get("/api/app/low-buy/400")
        bad_generic = self.client.get("/api/app/low-buy/500")
        self.assertEqual(not_found.status_code, 404)
        self.assertEqual(bad_source.status_code, 400)
        self.assertEqual(bad_generic.status_code, 500)

    def test_low_buy_favorite_route(self) -> None:
        response = self.client.post(
            "/api/app/low-buy/300750/favorite",
            json=AppLowBuyFavoriteRequest(name="宁德时代").model_dump(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["symbol"], "300750")

    def test_mutation_routes_return_explicit_response_shape(self) -> None:
        watchlist = self.client.post(
            "/api/app/watchlist",
            json={
                "symbol": "510300",
                "name": "沪深300ETF",
                "base_position": 1000,
                "available_position": 1000,
                "cost_basis": None,
                "memo": "",
            },
        )
        favorite = self.client.post(
            "/api/app/low-buy/300750/favorite",
            json=AppLowBuyFavoriteRequest(name="宁德时代").model_dump(),
        )
        self.assertEqual(set(watchlist.json().keys()), {"message", "symbol"})
        self.assertEqual(set(favorite.json().keys()), {"message", "symbol"})

    def test_openapi_contract_exposes_mutation_schema_and_scan_mode_enum(self) -> None:
        schema = self.app.openapi()
        watchlist_post = schema["paths"]["/api/app/watchlist"]["post"]
        favorite_post = schema["paths"]["/api/app/low-buy/{symbol}/favorite"]["post"]
        low_buy_get = schema["paths"]["/api/app/low-buy"]["get"]

        watchlist_schema = watchlist_post["responses"]["200"]["content"]["application/json"]["schema"]
        favorite_schema = favorite_post["responses"]["200"]["content"]["application/json"]["schema"]
        scan_mode_schema = next(
            parameter["schema"] for parameter in low_buy_get["parameters"] if parameter["name"] == "scan_mode"
        )

        self.assertEqual(watchlist_schema["$ref"], "#/components/schemas/AppMutationResponse")
        self.assertEqual(favorite_schema["$ref"], "#/components/schemas/AppMutationResponse")
        self.assertEqual(scan_mode_schema["enum"], ["quick", "full"])


if __name__ == "__main__":
    unittest.main()
