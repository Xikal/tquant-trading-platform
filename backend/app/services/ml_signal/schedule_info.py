from __future__ import annotations

from app.core.config import get_settings


def next_training_rule_text() -> str:
    settings = get_settings()
    weekday_map = {
        0: "周一",
        1: "周二",
        2: "周三",
        3: "周四",
        4: "周五",
        5: "周六",
        6: "周日",
    }
    weekday_text = weekday_map.get(settings.evolution_scheduler_weekday, f"weekday={settings.evolution_scheduler_weekday}")
    return (
        f"每{weekday_text} "
        f"{settings.evolution_scheduler_hour:02d}:{settings.evolution_scheduler_minute:02d} "
        "后由 runtime worker 自动触发一次 paper 增量训练与自进化检查。"
    )
