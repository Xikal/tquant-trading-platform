import type { IntradayMarketPulse, MarketBreadth, SectorRelativeStrengthResponse } from "../../types";
import type { CSSProperties } from "react";
import { Col, Row } from "antd";
import { MarketEmotionDashboard } from "./MarketEmotionDashboard";
import { SectorLeaderStrengthTable } from "./SectorLeaderStrengthTable";
import { WorkspacePageIntro } from "../workspace-shared/WorkspacePageIntro";

const MARKET_EMOTION_ROW_STYLE: CSSProperties = {
  marginLeft: 0,
  marginInline: 0,
  marginRight: 0,
  maxWidth: "100%",
  minWidth: 0,
  overflowX: "hidden",
  width: "100%",
};

const MARKET_EMOTION_PAGE_STYLE: CSSProperties = {
  display: "grid",
  gap: 10,
  minWidth: 0,
};

const MARKET_EMOTION_INTRO_STYLE: CSSProperties = {
  borderColor: "rgba(214, 165, 92, 0.28)",
};

export interface MarketEmotionPageProps {
  marketBreadth: MarketBreadth | null;
  marketPulse?: IntradayMarketPulse | null;
  sectorRelativeStrength: SectorRelativeStrengthResponse | null;
}

export function MarketEmotionPage({ marketBreadth, marketPulse, sectorRelativeStrength }: MarketEmotionPageProps) {
  return (
    <section style={MARKET_EMOTION_PAGE_STYLE}>
      <div className="panel" style={MARKET_EMOTION_INTRO_STYLE}>
        <WorkspacePageIntro
          title="市场情绪"
          summary={marketBreadth?.emotion_temperature_text || marketPulse?.emotion_text || "市场温度、龙头强度、板块轮动。"}
          more="这里解释盘面结构；午盘和收盘复盘仍回到实时监控页查看。"
          moreLabel="页面边界"
          tone={marketPulse?.data_quality === "fresh" ? "up" : marketPulse?.data_quality === "unavailable" ? "down" : marketPulse?.data_quality ? "warn" : "neutral"}
          pills={[
            { label: "情绪温度", value: marketBreadth?.emotion_temperature_text || "--" },
            { label: "龙头强度", value: marketPulse?.leader_strength_text || "--" },
            { label: "数据质量", value: marketBreadth?.data_quality_text || marketPulse?.data_quality_text || "--", tone: marketPulse?.data_quality === "fresh" ? "up" : marketPulse?.data_quality ? "warn" : "neutral" },
            { label: "板块数量", value: String(sectorRelativeStrength?.sector_count ?? "--") },
          ]}
        />
      </div>
      <Row gutter={[12, 12]} style={MARKET_EMOTION_ROW_STYLE}>
        <Col xs={24} xl={11}>
          <MarketEmotionDashboard marketBreadth={marketBreadth} marketPulse={marketPulse} />
        </Col>
        <Col xs={24} xl={13}>
          <SectorLeaderStrengthTable sectorRelativeStrength={sectorRelativeStrength} />
        </Col>
      </Row>
    </section>
  );
}
