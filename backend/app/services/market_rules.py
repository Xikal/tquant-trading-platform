from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Instrument, InstrumentRule
from app.models.schemas import TradingRuleOut
from app.services.etf.universe import T0_KEYWORDS, etf_profile_for, is_known_etf

ETF_THEME_KEYWORDS = {
    "证券": "券商/证券",
    "银行": "银行",
    "芯片": "半导体/芯片",
    "半导体": "半导体/芯片",
    "军工": "国防军工",
    "消费": "消费",
    "酒": "消费",
    "医药": "医药",
    "医疗": "医药",
    "新能源": "新能源",
    "光伏": "新能源",
    "煤炭": "煤炭",
    "红利": "红利",
    "央企": "央企/中字头",
    "科创": "科创成长",
    "创业板": "成长风格",
    "沪深300": "宽基",
    "中证500": "宽基",
    "中证1000": "宽基",
}


class MarketRuleService:
    def get_or_create_rule(self, db: Session, instrument: Instrument) -> TradingRuleOut:
        row = db.execute(
            select(InstrumentRule).where(InstrumentRule.symbol == instrument.symbol)
        ).scalar_one_or_none()
        if row is None:
            payload = self._derive_rule(instrument.symbol, instrument.name, instrument.instrument_type)
            row = InstrumentRule(symbol=instrument.symbol, **payload)
            db.add(row)
            db.commit()
            db.refresh(row)

        return TradingRuleOut(
            symbol=row.symbol,
            turnaround_mode=row.turnaround_mode,  # type: ignore[arg-type]
            supports_positive_t=row.supports_positive_t,
            supports_negative_t=row.supports_negative_t,
            same_day_sell_allowed=row.same_day_sell_allowed,
            requires_base_position=row.requires_base_position,
            notes=row.notes,
        )

    def build_runtime_notes(
        self,
        rule: TradingRuleOut,
        base_position: int,
        available_position: int,
    ) -> list[str]:
        notes: list[str] = []
        if rule.requires_base_position and base_position <= 0:
            notes.append("当前未提供底仓，股票/ETF 的底仓做T策略会被限制。")
        if available_position <= 0:
            notes.append("当前可卖数量为 0，反T或卖出型调仓无法执行。")
        if rule.turnaround_mode == "t1":
            notes.append("当前标的按 T+1 底仓做T逻辑处理，新买入部分不可当日卖出。")
        else:
            notes.append("当前标的按 T+0 / 可回转模式处理，可进行更灵活的日内回转。")
        return notes

    def _derive_rule(self, symbol: str, name: str, instrument_type: str) -> dict:
        profile = etf_profile_for(symbol, name=name, instrument_type=instrument_type)
        if profile is not None:
            theme = self.infer_etf_theme(name) if profile.category.value == "sector" else profile.category.value
            if profile.same_day_sell_allowed:
                return {
                    "turnaround_mode": "t0",
                    "supports_positive_t": True,
                    "supports_negative_t": True,
                    "same_day_sell_allowed": True,
                    "requires_base_position": False,
                    "notes": f"ETF universe 判定为可回转 ETF；分类 {theme}；{profile.notes}",
                }
            return {
                "turnaround_mode": "t1",
                "supports_positive_t": True,
                "supports_negative_t": True,
                "same_day_sell_allowed": False,
                "requires_base_position": True,
                "notes": f"ETF universe 未放行 T+0，默认按底仓做T模式处理；分类 {theme}；{profile.notes}",
            }

        return {
            "turnaround_mode": "t1",
            "supports_positive_t": True,
            "supports_negative_t": True,
            "same_day_sell_allowed": False,
            "requires_base_position": True,
            "notes": "A 股股票按底仓做T模式处理。",
        }

    @staticmethod
    def looks_like_etf(symbol: str, name: str = "") -> bool:
        return is_known_etf(symbol, name=name)

    @staticmethod
    def infer_etf_theme(name: str) -> str:
        for keyword, theme in ETF_THEME_KEYWORDS.items():
            if keyword in name:
                return theme
        return "宽基/未识别"
