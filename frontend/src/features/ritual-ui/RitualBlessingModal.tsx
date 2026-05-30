import { Button, Modal, Typography } from "antd";
import { useEffect } from "react";
import { ritualBlessingText, todayRitualKey } from "./ritualCopy";
import { dailyBlessingKey, isDailyBlessingSeen, markDailyBlessingSeen, useRitualPreference, useRitualUiStore } from "./ritualState";

interface RitualBlessingModalProps {
  enabled?: boolean;
  userId?: number | string;
  forceOpenForTest?: boolean;
}

export function RitualBlessingModal({ enabled, userId, forceOpenForTest = false }: RitualBlessingModalProps) {
  const preference = useRitualPreference();
  const visible = enabled ?? preference.enabled;
  const dayKey = todayRitualKey();
  const blessingOpen = useRitualUiStore((state) => state.blessingOpen);
  const openBlessing = useRitualUiStore((state) => state.openBlessing);
  const closeBlessing = useRitualUiStore((state) => state.closeBlessing);

  useEffect(() => {
    if (!visible || forceOpenForTest || isDailyBlessingSeen(dayKey, userId)) return;
    const timer = window.setTimeout(openBlessing, 600);
    return () => window.clearTimeout(timer);
  }, [dayKey, forceOpenForTest, openBlessing, userId, visible]);

  if (!visible) return null;

  if (forceOpenForTest && typeof window === "undefined") {
    return (
      <div className="ritual-blessing-modal">
        <strong>开盘祈愿</strong>
        <p>{ritualBlessingText()}</p>
        <span>这是红运仪式感视觉层，不参与策略、排序、交易或风控。</span>
      </div>
    );
  }

  function close() {
    markDailyBlessingSeen(dayKey, userId);
    closeBlessing();
  }

  return (
    <Modal
      className="ritual-blessing-modal"
      footer={<Button type="primary" onClick={close}>今日不再提示</Button>}
      onCancel={close}
      open={forceOpenForTest || blessingOpen}
      title="开盘祈愿"
      width={360}
    >
      <Typography.Paragraph>{ritualBlessingText()}</Typography.Paragraph>
      <Typography.Text type="secondary">
        这是红运仪式感视觉层，key {dailyBlessingKey(dayKey, userId)}，不参与策略、排序、交易或风控。
      </Typography.Text>
    </Modal>
  );
}
