import type { ReactNode } from "react";
import { Button } from "antd";
import { Panel } from "./Panel";
import { StatTile } from "../data";

export interface ConclusionItem {
  key: string;
  label: ReactNode;
  value: ReactNode;
  tone?: "up" | "down" | "warn" | "neutral";
  active?: boolean;
  helper?: ReactNode;
  onClick?: () => void;
}

interface ConclusionBarProps {
  actions?: ReactNode;
  items: ConclusionItem[];
  summary?: ReactNode;
  title?: ReactNode;
}

export function ConclusionBar({ actions, items, summary, title }: ConclusionBarProps) {
  return (
    <Panel className="tq-conclusion-bar" title={title} extra={actions}>
      {summary ? <div className="tq-conclusion-bar__summary">{summary}</div> : null}
      <div className="tq-conclusion-bar__grid">
        {items.map((item) => (
          <ConclusionBarItem key={item.key} item={item} />
        ))}
      </div>
    </Panel>
  );
}

function ConclusionBarItem({ item }: { item: ConclusionItem }) {
  const body = (
    <StatTile
      label={<span className="tq-conclusion-bar__label">{item.label}</span>}
      value={<span className={`tq-conclusion-bar__value tq-conclusion-bar__value--${item.tone || "neutral"}${item.active ? " tq-conclusion-bar__value--active" : ""}`.trim()}>{item.value}</span>}
    />
  );

  return (
    <div className={`tq-conclusion-bar__item ${item.onClick ? "tq-conclusion-bar__item--clickable" : ""}`.trim()}>
      {item.onClick ? (
        <Button
          type="text"
          className="tq-conclusion-bar__button"
          onClick={item.onClick}
          aria-pressed={item.active ? "true" : undefined}
        >
          {body}
        </Button>
      ) : body}
      {item.helper ? <div className="tq-conclusion-bar__helper">{item.helper}</div> : null}
    </div>
  );
}
