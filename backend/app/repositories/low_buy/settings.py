from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import SystemSetting


class SystemSettingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch(self, key: str) -> SystemSetting | None:
        return self.db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()

    def upsert(self, key: str, value: str) -> None:
        row = self.fetch(key)
        if row is None:
            self.db.add(SystemSetting(key=key, value=value))
            return
        row.value = value

