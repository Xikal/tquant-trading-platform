import type { ReactNode } from "react";
import { PriceText } from "./PriceText";
import type { PriceTone } from "./PriceText";

interface StatTileProps {
  delta?: number | null;
  deltaTone?: PriceTone;
  label: ReactNode;
  value: ReactNode;
}

export function StatTile({ delta, deltaTone, label, value }: StatTileProps) {
  return (
    <div className="tq-stat-tile">
      <div className="tq-stat-tile__label">{label}</div>
      <div className="tq-stat-tile__value">{value}</div>
      {typeof delta === "number" ? (
        <div className="tq-stat-tile__delta">
          <PriceText value={delta} tone={deltaTone} suffix="%" showSign />
        </div>
      ) : null}
    </div>
  );
}
