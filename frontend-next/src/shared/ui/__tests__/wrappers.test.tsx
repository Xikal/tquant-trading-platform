import type { ColumnDef } from "@tanstack/solid-table";
import { createSignal } from "solid-js";
import { render } from "solid-js/web";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FormField } from "../../form/FormField";
import { Button } from "../Button";
import { CommandPalette } from "../CommandPalette";
import { DataTable } from "../DataTable";
import { Modal } from "../Modal";
import { Panel } from "../Panel";
import { ShadowActionPanel } from "../ShadowActionPanel";
import { createToastStore } from "../Toast";
import { VirtualCardList } from "../VirtualList";

afterEach(() => {
  document.body.innerHTML = "";
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("shared wrapper accessibility", () => {
  it("keeps icon-only buttons nameable", () => {
    render(() => <Button iconOnly ariaLabel="刷新列表" />, document.body);

    expect(document.querySelector("button")?.getAttribute("aria-label")).toBe("刷新列表");
  });

  it("connects form field hints and validation errors", () => {
    render(() => <FormField label="股票代码" hint="6 位代码" error="代码无效" value="000001" />, document.body);

    const input = document.querySelector("input");
    expect(input?.getAttribute("aria-invalid")).toBe("true");
    expect(input?.getAttribute("aria-describedby")).toContain("hint");
    expect(input?.getAttribute("aria-describedby")).toContain("error");
  });

  it("supports keyboard row activation in DataTable", () => {
    const onRowClick = vi.fn();
    const columns: ColumnDef<{ symbol: string; name: string }>[] = [
      { accessorKey: "symbol", header: "代码" },
      { accessorKey: "name", header: "名称" },
    ];

    render(() => <DataTable data={[{ symbol: "000001", name: "平安银行" }]} columns={columns} onRowClick={onRowClick} />, document.body);

    const row = document.querySelector("tbody tr");
    row?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));

    expect(onRowClick).toHaveBeenCalledWith({ symbol: "000001", name: "平安银行" }, 0);
  });

  it("does not render an empty panel header when no header props are provided", () => {
    render(() => <Panel class="test-panel">内容</Panel>, document.body);

    expect(document.querySelector(".test-panel header")).toBeNull();
    expect(document.querySelector(".test-panel .tq-panel__title")).toBeNull();
    expect(document.querySelector(".test-panel .tq-panel__body")?.textContent).toContain("内容");
  });

  it("keeps the legacy panel header class contract when header props are provided", () => {
    render(() => (
      <Panel
        class="test-panel"
        title="标题"
        subtitle="副标题"
        actions={<button type="button">动作</button>}
      >
        内容
      </Panel>
    ), document.body);

    expect(document.querySelector(".test-panel .tq-panel__header")).not.toBeNull();
    expect(document.querySelector(".test-panel .tq-panel__title")?.textContent).toBe("标题");
    expect(document.querySelector(".test-panel .tq-panel__subtitle")?.textContent).toBe("副标题");
    expect(document.querySelector(".test-panel .tq-tag-row")?.textContent).toContain("动作");
  });

  it("traps modal focus, closes with Escape, and restores trigger focus", async () => {
    const TestModal = () => {
      const [open, setOpen] = createSignal(false);
      return (
        <>
          <button type="button" id="trigger" onClick={() => setOpen(true)}>
            打开
          </button>
          <Modal open={open()} title="确认操作" onClose={() => setOpen(false)}>
            <button type="button" id="confirm">
              确认
            </button>
          </Modal>
        </>
      );
    };

    render(() => <TestModal />, document.body);

    const trigger = document.querySelector<HTMLButtonElement>("#trigger");
    trigger?.focus();
    trigger?.click();
    await waitForMicrotask();

    const dialog = document.querySelector("[role='dialog']");
    expect(dialog).not.toBeNull();
    expect(dialog?.contains(document.activeElement)).toBe(true);

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await waitForMicrotask();

    expect(document.querySelector("[role='dialog']")).toBeNull();
    expect(document.activeElement?.id).toBe("trigger");
  });

  it("clears the pending dialog activation timer on early close", () => {
    vi.useFakeTimers();
    const clearTimeoutSpy = vi.spyOn(window, "clearTimeout");
    const removeListenerSpy = vi.spyOn(document, "removeEventListener");
    const TestModal = () => {
      const [open, setOpen] = createSignal(true);
      return (
        <>
          <button type="button" id="trigger" onClick={() => setOpen(true)}>
            打开
          </button>
          <Modal open={open()} title="确认操作" onClose={() => setOpen(false)}>
            <button type="button" id="confirm">
              确认
            </button>
          </Modal>
          <button type="button" id="close" onClick={() => setOpen(false)}>
            关闭
          </button>
        </>
      );
    };

    const dispose = render(() => <TestModal />, document.body);
    document.querySelector<HTMLButtonElement>("#close")?.click();
    dispose();

    expect(clearTimeoutSpy).toHaveBeenCalled();
    expect(removeListenerSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
  });

  it("keeps command palette focus managed and executes the active option", async () => {
    const onExecute = vi.fn();
    const TestPalette = () => {
      const [open, setOpen] = createSignal(false);
      return (
        <>
          <button type="button" id="palette-trigger" onClick={() => setOpen(true)}>
            命令
          </button>
          <CommandPalette
            open={open()}
            getOptions={(query) =>
              [
                { key: "monitor", label: "实时监控", hint: "监控 · /monitor" },
                { key: "analysis", label: `分析${query}`, hint: "量化分析" },
              ].filter((item) => `${item.label} ${item.hint}`.includes(query))
            }
            onClose={() => setOpen(false)}
            onExecute={onExecute}
          />
        </>
      );
    };

    render(() => <TestPalette />, document.body);

    const trigger = document.querySelector<HTMLButtonElement>("#palette-trigger");
    trigger?.focus();
    trigger?.click();
    await waitForMicrotask();

    const input = document.querySelector<HTMLInputElement>(".tq-command__input");
    expect(input).not.toBeNull();
    expect(input).toBe(document.activeElement);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(onExecute).toHaveBeenCalledWith(expect.objectContaining({ key: "monitor" }));

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await waitForMicrotask();

    expect(document.querySelector("[role='dialog']")).toBeNull();
    expect(document.activeElement?.id).toBe("palette-trigger");
  });

  it("replaces same-id toasts without letting the stale timer dismiss the replacement", async () => {
    vi.useFakeTimers();
    let store!: ReturnType<typeof createToastStore>;
    const dispose = render(() => {
      store = createToastStore();
      return null;
    }, document.body);

    store.show({ id: "trade", title: "旧消息", durationMs: 100 });
    await vi.advanceTimersByTimeAsync(50);
    store.show({ id: "trade", title: "新消息", durationMs: 100 });
    await vi.advanceTimersByTimeAsync(60);

    expect(store.messages()).toEqual([expect.objectContaining({ id: "trade", title: "新消息" })]);
    await vi.advanceTimersByTimeAsync(50);
    expect(store.messages()).toEqual([]);
    dispose();
  });

  it("renders virtual cards with list semantics", () => {
    render(
      () => (
        <VirtualCardList
          items={["A", "B"]}
          estimateSize={32}
          maxHeight={80}
          ariaLabel="观察列表"
          renderItem={(item) => <div>{item}</div>}
        />
      ),
      document.body,
    );

    expect(document.querySelector("[role='list']")?.getAttribute("aria-label")).toBe("观察列表");
    expect(document.querySelectorAll("[role='listitem']")).toHaveLength(2);
  });

  it("does not render every virtual card before the virtualizer measures the scroll container", () => {
    render(
      () => (
        <VirtualCardList
          items={Array.from({ length: 100 }, (_, index) => `Item ${index + 1}`)}
          estimateSize={40}
          maxHeight={80}
          overscan={1}
          initialItemLimit={4}
          ariaLabel="长观察列表"
          renderItem={(item) => <div>{item}</div>}
        />
      ),
      document.body,
    );

    expect(document.querySelectorAll("[role='listitem']").length).toBeLessThan(100);
  });

  it("refreshes shadow action drafts when parent fields change", async () => {
    const TestShadowAction = () => {
      const [symbol, setSymbol] = createSignal("000001");
      return (
        <>
          <button type="button" id="switch-symbol" onClick={() => setSymbol("600000")}>
            切换
          </button>
          <ShadowActionPanel
            title="观察池维护"
            actionLabel="保存观察"
            fields={[
              { key: "symbol", label: "代码", value: symbol() },
              { key: "reason", label: "理由", value: `观察 ${symbol()}` },
            ]}
          />
        </>
      );
    };

    render(() => <TestShadowAction />, document.body);

    expect(document.querySelector<HTMLInputElement>("input[aria-label='代码']")?.value).toBe("000001");
    document.querySelector<HTMLButtonElement>(".tq-shadow-action__footer button")?.click();
    expect(document.body.textContent).toContain("已进入二次确认");

    document.querySelector<HTMLButtonElement>("#switch-symbol")?.click();
    await waitForMicrotask();

    expect(document.querySelector<HTMLInputElement>("input[aria-label='代码']")?.value).toBe("600000");
    expect(document.body.textContent).toContain("等待确认");
  });

  it("prevents duplicate shadow action submissions while a submit is pending", async () => {
    vi.useFakeTimers();
    const onSubmit = vi.fn(
      () =>
        new Promise<string>((resolve) => {
          window.setTimeout(() => resolve("提交完成"), 100);
        }),
    );
    render(
      () => (
        <ShadowActionPanel
          title="重复提交"
          actionLabel="保存"
          fields={[{ key: "symbol", label: "代码", value: "000001" }]}
          onSubmit={onSubmit}
        />
      ),
      document.body,
    );

    const button = document.querySelector<HTMLButtonElement>(".tq-shadow-action__footer button");
    button?.click();
    button?.click();
    button?.click();

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(button?.disabled).toBe(true);
    expect(document.body.textContent).toContain("处理中");

    await vi.advanceTimersByTimeAsync(100);

    expect(document.body.textContent).toContain("提交完成");
    expect(button?.disabled).toBe(false);
  });

  it("shows shadow action submit failures without clearing the current draft", async () => {
    const onSubmit = vi.fn(async () => {
      throw new Error("后端契约缺失 access_token=secret-token-123 password=unsafe");
    });
    render(
      () => (
        <ShadowActionPanel
          title="失败恢复"
          actionLabel="保存"
          fields={[{ key: "symbol", label: "代码", value: "000001" }]}
          onSubmit={onSubmit}
        />
      ),
      document.body,
    );

    const button = document.querySelector<HTMLButtonElement>(".tq-shadow-action__footer button");
    button?.click();
    button?.click();
    await waitForMicrotask();

    expect(document.body.textContent).toContain("提交失败：后端契约缺失");
    expect(document.body.textContent).toContain("access_token=[redacted]");
    expect(document.body.textContent).toContain("password=[redacted]");
    expect(document.body.textContent).not.toContain("secret-token-123");
    expect(document.body.textContent).not.toContain("unsafe");
    expect(document.querySelector<HTMLInputElement>("input[aria-label='代码']")?.value).toBe("000001");
    expect(document.body.textContent).toContain("已确认");
  });
});

function waitForMicrotask() {
  return new Promise((resolve) => window.setTimeout(resolve, 0));
}
