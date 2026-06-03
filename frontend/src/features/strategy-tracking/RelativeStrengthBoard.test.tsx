import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RelativeStrengthBoard } from "./RelativeStrengthBoard";

describe("RelativeStrengthBoard", () => {
  it("renders disabled state without facts table", () => {
    const html = renderToStaticMarkup(
      <RelativeStrengthBoard
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

    expect(html).toContain("抗跌榜未开启");
  });

  it("renders no-data rows explicitly", () => {
    const html = renderToStaticMarkup(<RelativeStrengthBoard loading={false} data={{ enabled: true, total: 0, items: [], data_quality: "insufficient", as_of: "2026-05-24T15:10:00", engine_version: "trading-experience-v1", source: "daily_bar_snapshots", research_only: true }} />);

    expect(html).toContain("相对强度只展示信号日事实");
  });
});
