import { signal } from "@preact/signals-react";

export const topbarPulseSignal = signal(formatTopbarPulse());

export function updateTopbarPulse(value = formatTopbarPulse()): void {
  if (topbarPulseSignal.value !== value) {
    topbarPulseSignal.value = value;
  }
}

function formatTopbarPulse(): string {
  return new Date().toLocaleTimeString("zh-CN", {
    hour12: false,
    timeZone: "Asia/Shanghai",
  });
}
