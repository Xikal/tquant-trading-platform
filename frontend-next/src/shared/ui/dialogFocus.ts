import { onCleanup } from "solid-js";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export interface DialogFocusOptions {
  getContainer: () => HTMLElement | undefined;
  isOpen: () => boolean;
  onClose: () => void;
}

export function createDialogFocus(options: DialogFocusOptions) {
  let restoreTarget: HTMLElement | null = null;
  let activationTimer: number | null = null;

  function captureTrigger() {
    restoreTarget = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }

  function activate() {
    clearActivationTimer();
    activationTimer = window.setTimeout(() => {
      activationTimer = null;
      const container = options.getContainer();
      if (!container) return;
      const focusable = getFocusable(container);
      (focusable[0] ?? container).focus();
    }, 0);
  }

  function deactivate() {
    clearActivationTimer();
    restoreTarget?.focus();
    restoreTarget = null;
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (!options.isOpen()) return;
    if (event.key === "Escape") {
      event.preventDefault();
      options.onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const container = options.getContainer();
    if (!container) return;
    const focusable = getFocusable(container);
    if (focusable.length === 0) {
      event.preventDefault();
      container.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
      return;
    }
    if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  document.addEventListener("keydown", handleKeyDown);
  onCleanup(() => {
    clearActivationTimer();
    document.removeEventListener("keydown", handleKeyDown);
  });

  return {
    captureTrigger,
    activate,
    deactivate,
  };

  function clearActivationTimer() {
    if (activationTimer === null) return;
    window.clearTimeout(activationTimer);
    activationTimer = null;
  }
}

function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => {
    const style = window.getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden";
  });
}
