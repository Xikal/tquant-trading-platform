import { createEffect, createSignal, onCleanup } from "solid-js";

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function createReducedMotionSignal() {
  const [reducedMotion, setReducedMotion] = createSignal(prefersReducedMotion());

  createEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleChange = () => setReducedMotion(mediaQuery.matches);
    handleChange();
    mediaQuery.addEventListener("change", handleChange);
    onCleanup(() => mediaQuery.removeEventListener("change", handleChange));
  });

  return reducedMotion;
}

export function motionDuration(defaultMs: number, reducedMs = 0): number {
  return prefersReducedMotion() ? reducedMs : defaultMs;
}
