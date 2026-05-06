from __future__ import annotations

import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import FeatureFlagAuditLog, SystemSetting, User
from app.services.shared import feature_flags
from app.services.shared.feature_flags import (
    clear_feature_flag_cache,
    flag_to_dict,
    list_feature_flag_audit,
    list_feature_flags,
    update_feature_flag,
)


class FeatureFlagsServiceTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        clear_feature_flag_cache()

    def test_feature_flags_include_documented_response_fields(self) -> None:
        with self.Session() as db:
            items = [flag_to_dict(item) for item in list_feature_flags(db)]
            self.assertTrue(items)
            first = items[0]
            self.assertIn("value", first)
            self.assertIn("updated_at", first)
            self.assertIn("updated_by", first)

    def test_update_writes_operator_ip_audit_and_clears_cache(self) -> None:
        with self.Session() as db:
            user = User(username="admin", display_name="admin", password_hash="x", roles="admin")
            db.add(user)
            db.commit()

            before = feature_flags._CACHE_ITEMS  # type: ignore[attr-defined]
            self.assertIsNone(before)
            list_feature_flags(db)
            self.assertIsNotNone(feature_flags._CACHE_ITEMS)  # type: ignore[attr-defined]

            update_feature_flag(
                db,
                key="smart_mode_enabled",
                enabled=False,
                current_user=user,
                operator_ip="127.0.0.1",
            )
            self.assertIsNone(feature_flags._CACHE_ITEMS)  # type: ignore[attr-defined]

            audit = db.query(FeatureFlagAuditLog).filter_by(flag_key="smart_mode_enabled").one()
            self.assertEqual(audit.operator_ip, "127.0.0.1")
            rows = list_feature_flag_audit(db)
            self.assertEqual(rows[0]["operator_ip"], "127.0.0.1")

    def test_list_feature_flags_does_not_query_audit_log(self) -> None:
        with self.Session() as db:
            db.add(SystemSetting(key="ff_smart_mode_enabled", value="true"))
            db.add_all(
                FeatureFlagAuditLog(
                    flag_key="smart_mode_enabled",
                    old_value="false",
                    new_value="true",
                    operator_user_id=1,
                    operator_ip="127.0.0.1",
                )
                for _ in range(3)
            )
            db.commit()
            clear_feature_flag_cache()

            audit_queries: list[str] = []
            bind = db.get_bind()

            def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                if "feature_flag_audit_log" in statement.lower():
                    audit_queries.append(statement)

            event.listen(bind, "before_cursor_execute", before_cursor_execute)
            try:
                list_feature_flags(db)
            finally:
                event.remove(bind, "before_cursor_execute", before_cursor_execute)

            self.assertEqual(audit_queries, [])


if __name__ == "__main__":
    unittest.main()
