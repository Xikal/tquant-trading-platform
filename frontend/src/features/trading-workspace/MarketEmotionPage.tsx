import type { MarketBreadth, SectorRelativeStrengthResponse } from "../../types";
import { EmptyState, InfoPill, PanelTitle } from "./WorkspaceComponents";
import { formatPct, shortTime } from "./workspaceFormatters";

export interface MarketEmotionPageProps {
  marketBreadth: MarketBreadth | null;
  sectorRelativeStrength: SectorRelativeStrengthResponse | null;
}

export function MarketEmotionPage({ marketBreadth, sectorRelativeStrength }: MarketEmotionPageProps) {
  const leaders = sectorRelativeStrength?.items ?? [];
  return (
    <section className="page-grid emotion-page-grid">
      <div className="panel emotion-page-summary">
        <PanelTitle title="市场情绪仪表盘" actions={<span className="muted">更新 {shortTime(marketBreadth?.updated_at) || "--"}</span>} />
        <div className="context-row">
          <InfoPill label="情绪温度" value={marketBreadth?.emotion_temperature_text || "--"} tone={emotionTone(marketBreadth?.emotion_temperature_score)} />
          <InfoPill label="涨停/跌停" value={`${marketBreadth?.limit_up_count ?? "--"} / ${marketBreadth?.limit_down_count ?? "--"}`} />
          <InfoPill label="炸板率" value={formatRatioPct(marketBreadth?.broken_board_ratio)} tone={(marketBreadth?.broken_board_ratio ?? 0) > 0.25 ? "down" : "neutral"} />
          <InfoPill label="连板高度" value={String(marketBreadth?.board_height || "--")} />
          <InfoPill label="上涨比例" value={formatRatioPct(marketBreadth?.stock_up_ratio)} />
          <InfoPill label="热点行业" value={(marketBreadth?.hot_industries ?? []).slice(0, 3).join(" / ") || "--"} />
        </div>
        <div className="emotion-board-panel">
          <div className="limit-board-bars large">
            {buildBoardDistribution(marketBreadth?.board_height ?? 0).map((item) => (
              <span key={item.label} style={{ height: `${item.height}%` }}>
                <i>{item.label}</i>
              </span>
            ))}
          </div>
          <p className="hint">连板高度越高，说明短线情绪越活跃；炸板率过高时，低吸和做T都应降仓。</p>
        </div>
      </div>

      <div className="panel emotion-page-leaders">
        <PanelTitle title="实时龙头强度排行" actions={<span className="muted">{sectorRelativeStrength?.trade_date || "--"}</span>} />
        {leaders.length ? (
          <div className="emotion-leader-table">
            {leaders.slice(0, 30).map((item) => (
              <div key={`${item.sector_name}-${item.symbol}`} className="emotion-leader-row">
                <strong>{item.name} <small>{item.symbol}</small></strong>
                <span>{item.sector_name} #{item.rank}</span>
                <span>涨跌 {formatPct(item.change_pct)}</span>
                <span>量比 {item.volume_ratio.toFixed(2)}</span>
                <b>龙头分 {item.leader_score.toFixed(0)}</b>
              </div>
            ))}
          </div>
        ) : <EmptyState text="暂无板块龙头强度数据，等待市场快照刷新。" />}
      </div>
    </section>
  );
}

function emotionTone(score?: number): "up" | "warn" | "down" | "neutral" {
  if (typeof score !== "number") return "neutral";
  if (score >= 65) return "up";
  if (score >= 45) return "warn";
  return "down";
}

function formatRatioPct(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const normalized = Math.abs(value) <= 1 ? value * 100 : value;
  return `${normalized.toFixed(0)}%`;
}

function buildBoardDistribution(boardHeight: number): Array<{ label: string; height: number }> {
  const current = Math.max(0, Math.min(6, Math.round(boardHeight || 0)));
  return ["1板", "2板", "3板", "4板", "5+"].map((label, index) => ({
    label,
    height: Math.max(14, index + 1 <= current ? 34 + index * 13 : 14),
  }));
}
