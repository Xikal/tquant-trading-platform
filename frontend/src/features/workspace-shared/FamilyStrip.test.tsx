import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FamilyStrip } from "./FamilyStrip";

describe("FamilyStrip", () => {
  it("renders compact family tiles with data quality hints", () => {
    const html = renderToStaticMarkup(
      <FamilyStrip
        priorityBoard={{
          data_quality: "partial",
          data_quality_text: "部分候选缺行情",
          missing_strategies: ["leader_pullback_band"],
          family_sections: [
            {
              family_key: "leader_pullback_band",
              family_text: "龙头回踩波段",
              total_candidates: 2,
              immediate_count: 1,
              focus_count: 1,
              track_count: 0,
              avg_priority_score: 71,
              top_strategy_titles: ["龙头回踩波段"],
              performance: {
                family_key: "leader_pullback_band",
                family_text: "龙头回踩波段",
                strategy_count: 1,
                evaluated_signals: 20,
                filled_signals: 12,
                not_filled_signals: 8,
                hit_count: 9,
                net_win_rate: 18,
                avg_net_return_pct: 0.8,
                not_filled_rate: 40,
                stop_loss_rate: 10,
                hit_rate: 45,
              },
              items: [
                {
                  symbol: "600000",
                  name: "测试股份",
                  buy_signal_text: "接近买点",
                  strategy_titles: ["龙头回踩波段"],
                  data_quality: "fresh",
                },
              ],
            },
          ],
        } as never}
      />,
    );

    expect(html).toContain("龙头回踩波段");
    expect(html).toContain("2 只");
    expect(html).toContain("净胜优势 +18%");
    expect(html).toContain("部分候选缺行情");
    expect(html).toContain("查看明细");
  });
});
