import { afterEach, describe, expect, it, vi } from "vitest";
import { installWorkspaceShortcuts } from "./keyboardShortcuts";
import { nextRoutes } from "../shared/config/routes";

describe("installWorkspaceShortcuts", () => {
  const cleanups: Array<() => void> = [];

  afterEach(() => {
    while (cleanups.length) cleanups.pop()?.();
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  it("opens the command palette from Cmd/Ctrl+K", () => {
    const openCommandPalette = vi.fn();
    const navigate = vi.fn();
    cleanups.push(installWorkspaceShortcuts({ navigate, openCommandPalette }));

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));

    expect(openCommandPalette).toHaveBeenCalledTimes(1);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("routes Cmd/Ctrl+number to the configured core pages", () => {
    const openCommandPalette = vi.fn();
    const navigate = vi.fn();
    cleanups.push(installWorkspaceShortcuts({ navigate, openCommandPalette }));

    const commandRoutes = nextRoutes.filter((item) => item.commandIndex);
    for (const route of commandRoutes) {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: String(route.commandIndex), ctrlKey: true }));
    }

    expect(navigate).toHaveBeenCalledTimes(commandRoutes.length);
    expect(navigate.mock.calls.map(([options]) => options)).toEqual(
      commandRoutes.map((route) => ({ to: route.path })),
    );
    expect(openCommandPalette).not.toHaveBeenCalled();
  });

  it("does not trigger global shortcuts from editable fields", () => {
    const openCommandPalette = vi.fn();
    const navigate = vi.fn();
    const input = document.createElement("input");
    const textarea = document.createElement("textarea");
    const select = document.createElement("select");
    const editable = document.createElement("div");
    editable.contentEditable = "true";
    document.body.append(input, textarea, select, editable);
    cleanups.push(installWorkspaceShortcuts({ navigate, openCommandPalette }));

    input.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
    textarea.dispatchEvent(new KeyboardEvent("keydown", { key: "1", ctrlKey: true, bubbles: true }));
    select.dispatchEvent(new KeyboardEvent("keydown", { key: "2", ctrlKey: true, bubbles: true }));
    editable.dispatchEvent(new KeyboardEvent("keydown", { key: "3", ctrlKey: true, bubbles: true }));

    expect(openCommandPalette).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });
});
