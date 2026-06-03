import { QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { createAppQueryClient } from "../../state/queryClient";
import { TradeJournalPanel } from "./TradeJournalPanel";
import { TradeJournalQuickEntry } from "./TradeJournalQuickEntry";

describe("TradeJournalPanel", () => {
  it("hides quick entry when the journal flag is off", () => {
    const html = renderToStaticMarkup(
      <TradeJournalPanel
        loading={false}
        data={{
          enabled: false,
          total: 0,
          items: [],
          data_quality: "blocked",
          as_of: "2026-05-24T15:10:00",
          engine_version: "trading-experience-v1",
          source: "feature_flag",
          research_only: true,
        }}
      />,
    );

    expect(html).toContain("纪律日志未开启");
    expect(html).not.toContain("保存记录");
  });

  it("renders quick entry and virtualized journal cards without instruction copy", () => {
    const html = renderToStaticMarkup(
      <QueryClientProvider client={createAppQueryClient()}>
        <TradeJournalPanel
          accountId={1}
          loading={false}
          data={{
            enabled: true,
            total: 1,
            data_quality: "ok",
            as_of: "2026-05-24T15:10:00",
            engine_version: "trading-experience-v1",
            source: "trade_journal",
            research_only: true,
            items: [{
              entry_id: 1,
              user_id: 1,
              account_id: 1,
              symbol: "600000",
              action: "note",
              reason_text: "收盘后纪律复核",
              signal_source: "manual_review",
              discipline_flags: { stop_loss_set: true },
              mistake_tags: ["late_plan"],
              data_quality: "ok",
              as_of: "2026-05-24T15:10:00",
              engine_version: "trading-experience-v1",
              source: "manual",
              research_only: true,
              created_at: "2026-05-24T15:10:00",
              updated_at: "2026-05-24T15:10:00",
            }],
          }}
        />
      </QueryClientProvider>,
    );

    expect(html).toContain("保存记录");
    expect(html).toContain("收盘后纪律复核");
    expect(html).not.toContain("加仓");
    expect(html).not.toContain("推荐");
  });

  it("submits normalized payload from quick entry", () => {
    const html = renderToStaticMarkup(
      <TradeJournalQuickEntry accountId={1} submitting={false} errorText="提交失败" onSubmit={() => undefined} />,
    );

    expect(html).toContain("提交失败");
    expect(html).toContain("复盘理由");
    expect(html).toContain("记录类型");
    expect(html).not.toContain("加仓");
  });
});
