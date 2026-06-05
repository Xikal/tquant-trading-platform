import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { CommandPalette } from "./CommandPalette";

vi.mock("../../stores/workspaceStore", () => ({
  useWorkspaceStore: (selector: (state: { commandQuery: string; setCommandQuery: (query: string) => void }) => unknown) =>
    selector({ commandQuery: "", setCommandQuery: vi.fn() }),
}));

describe("CommandPalette", () => {
  it("does not surface dense page hierarchy copy for strategy, backtest, and data entries", () => {
    const queryClient = new QueryClient();
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <CommandPalette
          open
          strategies={[]}
          onAnalyzeSymbol={vi.fn()}
          onClose={vi.fn()}
          onNavigate={vi.fn()}
          onOpenStrategy={vi.fn()}
        />
      </QueryClientProvider>,
    );

    expect(html).toContain("打开策略跟踪页面");
    expect(html).toContain("打开回测页面");
    expect(html).toContain("打开数据页面");
    expect(html).not.toContain("信号表现、复盘、抗跌事实");
    expect(html).not.toContain("24个月报告和组合收益");
    expect(html).not.toContain("数据源、覆盖率、补数任务");
  });
});
