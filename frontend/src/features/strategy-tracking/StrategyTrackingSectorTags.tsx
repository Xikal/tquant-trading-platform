import { Tag } from "antd";

interface StrategyTrackingSectorTagsProps {
  sectors: string[];
  boardType?: string;
  boardText?: string;
  max?: number;
}

export function StrategyTrackingSectorTags({ sectors = [], boardType, boardText, max = 3 }: StrategyTrackingSectorTagsProps) {
  const visible = sectors.slice(0, max);
  const remaining = Math.max(0, sectors.length - visible.length);
  if (!visible.length && !boardText) {
    return <span className="strategy-tracking-sector-empty">板块数据不足</span>;
  }
  return (
    <div className="strategy-tracking-sector-tags">
      {visible.map((sector) => (
        <Tag key={sector} color={sectorColor(sector, boardType, boardText)}>{sector}</Tag>
      ))}
      {remaining ? <Tag>+{remaining}</Tag> : null}
    </div>
  );
}

function sectorColor(sector: string, boardType?: string, boardText?: string): string {
  if (sector === boardText && boardType === "chinext") return "orange";
  if (sector === boardText && boardType === "star") return "purple";
  if (sector.includes("创业板")) return "orange";
  if (sector.includes("科创板")) return "purple";
  if (sector.includes("北交所")) return "cyan";
  return "default";
}
