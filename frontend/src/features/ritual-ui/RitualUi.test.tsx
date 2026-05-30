import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  RitualBlessingModal,
  RitualCloseBag,
  RitualFortuneStrip,
  RitualLuckyDraw,
  RitualSignalSeal,
  ritualFortuneText,
  ritualSealCopy,
  stableRitualIndex,
} from "./index";

describe("ritual-ui", () => {
  it("keeps daily fortune copy stable for the same date and tone", () => {
    const date = new Date("2026-05-29T09:30:00+08:00");

    expect(ritualFortuneText("neutral", date)).toBe(ritualFortuneText("neutral", date));
    expect(stableRitualIndex("same-seed", 5)).toBe(stableRitualIndex("same-seed", 5));
  });

  it("maps existing signal states to visual seals only", () => {
    expect(ritualSealCopy("buy_now").label).toBe("买点已至");
    expect(ritualSealCopy("near_entry").label).toBe("火候未到");
    expect(ritualSealCopy("buy_now", "stop").label).toBe("过火勿追");
  });

  it("renders fortune strip and hides it when disabled", () => {
    const enabledHtml = renderToStaticMarkup(<RitualFortuneStrip enabled marketTone="neutral" showCalendarHint />);
    const disabledHtml = renderToStaticMarkup(<RitualFortuneStrip enabled={false} marketTone="neutral" />);

    expect(enabledHtml).toContain("今日红运");
    expect(enabledHtml).toContain("宜");
    expect(disabledHtml).toBe("");
  });

  it("renders red seal and hides it when disabled", () => {
    const enabledHtml = renderToStaticMarkup(<RitualSignalSeal enabled signalState="buy_now" />);
    const disabledHtml = renderToStaticMarkup(<RitualSignalSeal enabled={false} signalState="buy_now" />);

    expect(enabledHtml).toContain("买点已至");
    expect(disabledHtml).toBe("");
  });

  it("renders lucky draw, opening blessing and close bag components", () => {
    const drawHtml = renderToStaticMarkup(<RitualLuckyDraw enabled />);
    const blessingHtml = renderToStaticMarkup(<RitualBlessingModal enabled forceOpenForTest userId={1} />);
    const closeHtml = renderToStaticMarkup(<RitualCloseBag enabled visible />);

    expect(drawHtml).toContain("幸运签");
    expect(blessingHtml).toContain("开盘祈愿");
    expect(blessingHtml).toContain("不参与策略、排序、交易或风控");
    expect(closeHtml).toContain("今日收盘福袋");
  });
});
