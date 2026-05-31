import { Button } from "antd";
import type { StrategyTrackingItem } from "../../types";

interface StrategyTrackingStatusCardsProps {
  items: StrategyTrackingItem[];
  activeStatus: string;
  onSelectStatus: (status: string) => void;
}

const STATUS_META = [
  { key: "focus", label: "可以重点看", text: "已到买点且风险线未破" },
  { key: "wait_entry", label: "还没到价", text: "信号后还没到计划买入区" },
  { key: "weakening", label: "已经走弱", text: "已跌破风险线或支撑" },
  { key: "review_needed", label: "需要复核", text: "数据异常、收益异常或样本不足" },
];

export function StrategyTrackingStatusCards({ items, activeStatus, onSelectStatus }: StrategyTrackingStatusCardsProps) {
  const total = items.length || 0;
  return (
    <section className="strategy-tracking-status-grid">
      {STATUS_META.map((item) => {
        const count = items.filter((row) => row.user_friendly_status === item.key).length;
        const pct = total ? Math.round((count / total) * 100) : 0;
        return (
          <Button
            key={item.key}
            className="strategy-tracking-status-card"
            type={activeStatus === item.key ? "primary" : "default"}
            onClick={() => onSelectStatus(activeStatus === item.key ? "" : item.key)}
          >
            <span>{item.label}</span>
            <strong>{count}</strong>
            <small>{pct}% · {item.text}</small>
          </Button>
        );
      })}
    </section>
  );
}
