import { describe, expect, it } from "vitest";

import { signalStateHelpText, signalStateKindText, signalStateText } from "./signalStateCopy";

describe("signalStateCopy", () => {
  it("keeps observation states explicit and out of buy recommendation wording", () => {
    const nearEntry = [
      signalStateText({ signal_state: "near_entry", signal_text: "" }),
      signalStateKindText("near_entry"),
      signalStateHelpText("near_entry"),
    ].join(" ");
    const observeConfirmed = [
      signalStateText({ signal_state: "observe_confirmed", signal_text: "" }),
      signalStateKindText("observe_confirmed"),
      signalStateHelpText("observe_confirmed"),
    ].join(" ");

    expect(nearEntry).toContain("观察");
    expect(nearEntry).toContain("不是买入");
    expect(observeConfirmed).toContain("观察");
    expect(observeConfirmed).toContain("不是买入");
    expect(`${nearEntry} ${observeConfirmed}`).not.toContain("买入推荐");
  });

  it("keeps buy-class copy limited to buy states", () => {
    expect(signalStateKindText("buy_now")).toContain("买入类");
    expect(signalStateKindText("soft_buy_now")).toContain("买入类");
    expect(signalStateKindText("watch")).not.toContain("买入类");
  });
});
