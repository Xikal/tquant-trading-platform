import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AnalysisPage } from "../analysis/AnalysisPage";

describe("AnalysisPage", () => {
  it("uses semantic layout classes for the analysis workspace", () => {
    const html = renderToStaticMarkup(
      <AnalysisPage
        draft={{
          symbol: "510300",
          prefer_strategy: "auto",
          base_position: "3000",
          available_position: "3000",
          cost_basis: "",
        }}
        setDraft={vi.fn()}
        result={null}
        anomaly={null}
        batchSymbols=""
        setBatchSymbols={vi.fn()}
        batchResults={[]}
        loading=""
        onRun={vi.fn()}
        onBatchRun={vi.fn()}
        onOpenPaperOrder={vi.fn()}
      />,
    );

    expect(html).toContain("tq-analysis-page");
    expect(html).toContain("tq-analysis-page__hero");
    expect(html).toContain("tq-analysis-page__identity");
    expect(html).toContain("tq-analysis-page__control");
    expect(html).toContain("tq-analysis-page__batch");
    expect(html).toContain("tq-analysis-page__decision");
    expect(html).toContain("tq-analysis-page__chart");
    expect(html).toContain("tq-analysis-page__plan");
  });
});
