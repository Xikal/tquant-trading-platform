import { Button, Popover, Typography } from "antd";
import { ritualLuckyDrawText, todayRitualKey } from "./ritualCopy";
import { useRitualPreference, useRitualUiStore } from "./ritualState";

interface RitualLuckyDrawProps {
  enabled?: boolean;
  compact?: boolean;
}

export function RitualLuckyDraw({ enabled, compact = false }: RitualLuckyDrawProps) {
  const preference = useRitualPreference();
  const visible = enabled ?? preference.enabled;
  const drawCount = useRitualUiStore((state) => state.drawCount);
  const drawLucky = useRitualUiStore((state) => state.drawLucky);
  if (!visible) return null;
  const draw = ritualLuckyDrawText(`${todayRitualKey()}:${drawCount}`);
  return (
    <Popover
      trigger="click"
      title={draw.title}
      content={<Typography.Text>{draw.content}</Typography.Text>}
    >
      <Button
        className="ritual-lucky-draw"
        size="small"
        type="text"
        onClick={drawLucky}
        title="抽一支只做仪式感的幸运签"
      >
        {compact ? "签" : "幸运签"}
      </Button>
    </Popover>
  );
}
