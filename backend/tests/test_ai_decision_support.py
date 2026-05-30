from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import SystemSetting
from app.models.schemas import AiDecisionSupportRequest
from app.models.schema_defs.analysis import AiInsight
from app.services.ai_decision_support import AiDecisionSupportService
from app.services.ai_service import AiService


class AiDecisionSupportTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)

    def test_unconfigured_model_returns_quant_fallback(self) -> None:
        with self.Session() as db:
            db.add_all(
                [
                    SystemSetting(key="llm_api_key", value=""),
                    SystemSetting(key="llm_model", value=""),
                    SystemSetting(key="llm_base_url", value=""),
                    SystemSetting(key="llm_provider", value="auto"),
                ]
            )
            db.commit()
            response = AiDecisionSupportService().explain(
                db,
                AiDecisionSupportRequest(
                    task="stock_explain",
                    title="测试个股",
                    payload={"symbol": "000001", "api_key": "must-not-leak"},
                ),
            )

        self.assertFalse(response.insight.enabled)
        self.assertEqual(response.title, "测试个股")
        self.assertIn("未配置大模型", response.insight.summary)

    def test_payload_sanitization_removes_sensitive_keys(self) -> None:
        service = AiDecisionSupportService()
        payload = service._build_payload(
            AiDecisionSupportRequest(
                task="daily_review",
                payload={
                    "items": [{"symbol": "000001"} for _ in range(20)],
                    "password": "secret",
                    "nested": {"token": "secret", "safe": "ok"},
                },
            )
        )
        context = payload["context"]

        self.assertEqual(len(context["items"]), 12)
        self.assertNotIn("password", context)
        self.assertNotIn("token", context["nested"])
        self.assertEqual(context["nested"]["safe"], "ok")

    def test_priority_board_unconfigured_model_returns_readable_quant_summary(self) -> None:
        with self.Session() as db:
            db.add_all(
                [
                    SystemSetting(key="llm_api_key", value=""),
                    SystemSetting(key="llm_model", value=""),
                    SystemSetting(key="llm_base_url", value=""),
                    SystemSetting(key="llm_provider", value="auto"),
                ]
            )
            db.commit()
            response = AiDecisionSupportService().explain(
                db,
                AiDecisionSupportRequest(
                    task="priority_board_summary",
                    title="榜单解读",
                    payload={
                        "market_state_text": "市场状态：缩量观望。",
                        "hot_industries": ["电力", "汽车零部件"],
                        "total_candidates": 12,
                        "immediate_count": 2,
                        "focus_count": 4,
                        "items": [
                            {"symbol": "000001", "name": "样本A", "buy_signal_text": "确定买入", "priority_score": 91},
                            {"symbol": "000002", "name": "样本B", "buy_signal_text": "接近买点", "priority_score": 86},
                        ],
                    },
                ),
            )

        self.assertFalse(response.insight.enabled)
        self.assertIn("确定买入 2 只", response.insight.summary)
        self.assertIn("样本A", response.insight.suggestions[0])
        self.assertIn("可以小仓", response.fixed_sections.can_buy)
        self.assertTrue(response.fixed_sections.tomorrow_plan)

    def test_priority_board_payload_keeps_compact_items_when_large(self) -> None:
        service = AiDecisionSupportService()
        oversized_text = "x" * 1200
        payload = service._build_payload(
            AiDecisionSupportRequest(
                task="priority_board_summary",
                payload={
                    "updated_at": "2026-04-28 10:00:00",
                    "market_state_text": "修复中",
                    "stock_up_ratio": 0.56,
                    "irrelevant_blob": oversized_text,
                    "items": [
                        {
                            "symbol": f"00000{index}",
                            "name": f"样本{index}",
                            "strategy_titles": ["原始低吸", "均线支撑"],
                            "latest_price": 10 + index,
                            "priority_score": 80 + index,
                            "unused_long_field": oversized_text,
                        }
                        for index in range(20)
                    ],
                },
            )
        )
        context = payload["context"]

        self.assertEqual(len(context["items"]), 5)
        self.assertEqual(context["items"][0]["symbol"], "000000")
        self.assertIn("strategy_titles", context["items"][0])
        self.assertNotIn("unused_long_field", context["items"][0])
        self.assertEqual(context["items_count_sent_to_ai"], 5)

    def test_ai_text_list_normalization_does_not_split_strings_into_chars(self) -> None:
        items = AiService._normalize_text_list("优先处理：A\n重点观察：B", limit=10)

        self.assertEqual(items, ["优先处理：A", "重点观察：B"])

    def test_deepseek_request_omits_forced_json_response_format(self) -> None:
        deepseek_body = AiService._build_request_body(
            "openai",
            "deepseek-v4-pro",
            {"task": "priority_board_summary"},
            "只返回 JSON",
            max_tokens=700,
        )
        compatible_body = AiService._build_request_body(
            "openai",
            "qwen-plus",
            {"task": "priority_board_summary"},
            "只返回 JSON",
            max_tokens=700,
        )

        self.assertNotIn("response_format", deepseek_body)
        self.assertEqual(compatible_body["response_format"], {"type": "json_object"})

    def test_provider_override_controls_request_mode(self) -> None:
        self.assertEqual(AiService._resolve_request_mode("https://example.com/v1", "anthropic"), "anthropic")
        self.assertEqual(AiService._resolve_request_mode("https://example.com/anthropic", "auto"), "anthropic")
        self.assertEqual(AiService._resolve_request_mode("https://example.com/v1", "openai_compatible"), "openai")

    def test_event_risk_llm_output_rejects_buy_sell_advice(self) -> None:
        service = AiDecisionSupportService()
        unsafe = AiInsight(
            enabled=True,
            summary="可以直接买入并加仓，止损可以放宽。",
            confidence=0.9,
            suggestions=["明天直接买入", "跌破止损也先拿着"],
            warnings=["无需关注减持"],
            raw={"source": "unit-test"},
        )

        guarded = service._guard_insight_output("event_risk_summary", unsafe)

        self.assertFalse(guarded.enabled)
        self.assertIn("拒绝", guarded.summary)
        self.assertNotIn("直接买入", guarded.summary)
        self.assertTrue(all("买入" not in item for item in guarded.suggestions))
        self.assertTrue(any("买卖建议" in item for item in guarded.warnings))


if __name__ == "__main__":
    unittest.main()
