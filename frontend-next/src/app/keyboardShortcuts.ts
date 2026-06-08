import type { NavigateFn } from "@tanstack/solid-router";
import { nextRoutes } from "../shared/config/routes";

export function installWorkspaceShortcuts(options: { navigate: NavigateFn; openCommandPalette: () => void }) {
  const onKeyDown = (event: KeyboardEvent) => {
    const meta = event.metaKey || event.ctrlKey;
    if (!meta) return;
    if (isEditableTarget(event.target)) return;
    const key = event.key.toLowerCase();
    if (key === "k") {
      event.preventDefault();
      options.openCommandPalette();
      return;
    }
    const index = Number(key);
    if (Number.isInteger(index) && index >= 1 && index <= 8) {
      const route = nextRoutes.find((item) => item.commandIndex === index);
      if (route) {
        event.preventDefault();
        void options.navigate({ to: route.path });
      }
    }
  };
  window.addEventListener("keydown", onKeyDown);
  return () => window.removeEventListener("keydown", onKeyDown);
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tagName = target.tagName.toLowerCase();
  return (
    target.isContentEditable ||
    target.contentEditable === "true" ||
    target.getAttribute("contenteditable") === "true" ||
    Boolean(target.closest("[contenteditable='true']")) ||
    tagName === "input" ||
    tagName === "textarea" ||
    tagName === "select"
  );
}
