import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { initialBacktestForm } from "./backtestForms";
import { BacktestSubmitPanel } from "./BacktestSubmitPanel";

describe("BacktestSubmitPanel", () => {
  it("renders expert position controls as a compact two-column grid", () => {
    const html = renderToStaticMarkup(
      <BacktestSubmitPanel
        form={initialBacktestForm}
        loading=""
        error=""
        notice=""
        mode="expert"
        strategyOptions={[["first_board", "首板回调"]]}
        onModeChange={vi.fn()}
        onFormChange={vi.fn()}
        onSubmit={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    expect(html).toContain("单票仓位");
    expect(html).toContain("最大持仓数");
    expect(html).toContain("日亏损暂停");
    expect(html).toContain("单笔上限");
    expect(html).toContain("最低现金保留");
    expect(html).toContain("grid-template-columns:repeat(2, minmax(0, 1fr))");
    expect(html).toContain("gap:6px 8px");
  });
});
