from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import StrategyMetadata, SystemSetting, User
from app.models.schema_defs.strategy_meta import StrategyGovernanceMutationRequest
from app.repositories.low_buy import SystemSettingRepository
from app.services.shared.feature_flags import clear_feature_flag_cache
from app.services.low_buy.strategy_auto_governance import (
    AUTO_GOVERNANCE_SETTING_KEY,
    refresh_low_buy_strategy_auto_governance,
)
from app.services.strategy_metadata_service import StrategyMetadataService


class StrategyMetadataServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_feature_flag_cache()
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)

    def test_promote_rejects_seed_strategy_with_pending_probe(self) -> None:
        with self.Session() as db:
            user = User(username="admin", display_name="admin", password_hash="x", roles="admin")
            db.add(user)
            db.commit()

            with self.assertRaisesRegex(ValueError, "策略探针状态"):
                StrategyMetadataService(db).promote_strategy(
                    StrategyGovernanceMutationRequest(
                        strategy_key="leader_pullback_band",
                        target_tier="core",
                        reason="测试提升",
                    ),
                    current_user=user,
                )

    def test_promote_rejects_unknown_strategy_key(self) -> None:
        with self.Session() as db:
            user = User(username="admin", display_name="admin", password_hash="x", roles="admin")
            db.add(user)
            db.commit()

            with self.assertRaisesRegex(ValueError, "未知策略"):
                StrategyMetadataService(db).promote_strategy(
                    StrategyGovernanceMutationRequest(
                        strategy_key="typo_strategy",
                        target_tier="auxiliary",
                        reason="测试提升",
                    ),
                    current_user=user,
                )

    def test_default_presets_follow_strategy_feature_flags(self) -> None:
        with self.Session() as db:
            db.add(SystemSetting(key="ff_strategy_volume_shrink_enabled", value="false"))
            db.commit()

            presets = StrategyMetadataService(db).list_presets().presets
            self.assertTrue(presets)
            for preset in presets:
                self.assertNotIn("volume_shrink", preset.config.get("strategies", []))
                self.assertIn("first_board", preset.config.get("strategies", []))

    def test_backtest_access_rejects_factor_for_ordinary_user(self) -> None:
        with self.Session() as db:
            user = User(username="user", display_name="user", password_hash="x", roles="")
            db.add_all([
                user,
                StrategyMetadata(
                    key="custom_factor",
                    display_name="测试因子",
                    category="factor",
                    enabled=True,
                    visibility="full",
                    probe_status="not_required",
                ),
            ])
            db.commit()

            with self.assertRaisesRegex(PermissionError, "因子"):
                StrategyMetadataService(db).validate_backtest_strategy_access(
                    ["custom_factor"],
                    current_user=user,
                )

    def test_backtest_access_allows_factor_for_research_user(self) -> None:
        with self.Session() as db:
            user = User(username="research", display_name="research", password_hash="x", roles="backtest_research")
            db.add_all([
                user,
                StrategyMetadata(
                    key="custom_factor",
                    display_name="测试因子",
                    category="factor",
                    enabled=True,
                    visibility="full",
                    probe_status="not_required",
                ),
            ])
            db.commit()

            StrategyMetadataService(db).validate_backtest_strategy_access(
                ["custom_factor"],
                current_user=user,
            )

    def test_backtest_access_rejects_backtest_only_for_ordinary_user(self) -> None:
        with self.Session() as db:
            user = User(username="user", display_name="user", password_hash="x", roles="")
            db.add(user)
            db.commit()

            with self.assertRaisesRegex(PermissionError, "研究回测"):
                StrategyMetadataService(db).validate_backtest_strategy_access(
                    ["leader_pullback_band"],
                    current_user=user,
                )

    def test_auto_governance_marks_new_auxiliary_strategy_watch_until_evidence_exists(self) -> None:
        with self.Session() as db:
            payload = refresh_low_buy_strategy_auto_governance(db)
            item = payload["items"]["mainline_limitup_shrink_retrace_reclaim"]

            self.assertEqual(item["status"], "watch")
            self.assertEqual(item["source"], "evidence_gate")
            self.assertIn("真实成交样本不足", item["reason"])

            persisted = SystemSettingRepository(db).fetch(AUTO_GOVERNANCE_SETTING_KEY)
            self.assertIsNotNone(persisted)


if __name__ == "__main__":
    unittest.main()
