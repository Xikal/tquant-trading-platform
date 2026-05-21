import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { MonitorPage } from "../monitor/MonitorPage";

describe("MonitorPage", () => {
  it("puts the direct action card before numeric metrics", () => {
    const html = renderToStaticMarkup(
      <MonitorPage
        priorityBoard={null}
        marketBreadth={null}
        sectorRelativeStrength={null}
        keyLevelAlerts={[]}
        sectorEtfT0={null}
        pairedHedge={null}
        priorityCards={[]}
        watchCards={[{
          name: "农业银行",
          symbol: "601288",
          priceText: "4.320",
          changeText: "+1.20%",
          riskText: "低风险",
          actionText: "正T",
          details: "接近支撑，等待承接确认。",
          executionHint: "冲高变弱先卖一部分。",
          tone: "up",
        }]}
        runtime={null}
        instrumentSyncStatus={null}
        watchDraft={{ symbol: "", name: "", base_position: "", available_position: "", cost_basis: "", memo: "" }}
        setWatchDraft={vi.fn()}
        editingWatchSymbol=""
        loading=""
        onRefresh={vi.fn()}
        onSync={vi.fn()}
        onAi={vi.fn()}
        onGoPlaybook={vi.fn()}
        onSelect={vi.fn()}
        onAnalyze={vi.fn()}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
        onAddWatchlist={vi.fn()}
        onCancelEdit={vi.fn()}
      />
    );

    expect(html).toContain("今天最重要的 1 件事");
    expect(html).toContain("农业银行");
    expect(html).toContain("展开盘面数字摘要");
  });
});
