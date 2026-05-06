from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import SystemSetting, User
from app.models.schema_defs.strategy_meta import StrategyGovernanceMutationRequest
from app.services.strategy_metadata_service import StrategyMetadataService


class StrategyMetadataServiceTests(unittest.TestCase):
    def setUp(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
