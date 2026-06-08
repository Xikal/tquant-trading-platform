import type { JSX } from "solid-js";

export const SIDEBAR_WIDTH = 220;
export const SIDEBAR_COLLAPSED_WIDTH = 64;
export const LEGACY_CONTENT_MAX_WIDTH = 1440;

export const workspaceShellStyle: JSX.CSSProperties = {
  "min-height": "100vh",
  background: "var(--bg-base)",
};

export const sidebarStyle: JSX.CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  bottom: 0,
  width: `${SIDEBAR_WIDTH}px`,
  display: "flex",
  "flex-direction": "column",
  background: "var(--brand-ink)",
  "z-index": 101,
  overflow: "hidden",
};

export const sidebarInnerStyle: JSX.CSSProperties = {
  display: "flex",
  "flex-direction": "column",
  height: "100%",
  "min-height": 0,
};

export const contentColumnStyle: JSX.CSSProperties = {
  "margin-left": `${SIDEBAR_WIDTH}px`,
  "min-height": "100vh",
  display: "flex",
  "flex-direction": "column",
};

export const contentMainStyle: JSX.CSSProperties = {
  flex: 1,
  "min-width": 0,
  "overflow-x": "hidden",
  padding: "var(--sp-5)",
};

export const contentMainArtifactStyle: JSX.CSSProperties = {
  ...contentMainStyle,
  "min-height": "calc(100vh - 48px)",
  padding: "12px",
};

export const contentInnerStyle: JSX.CSSProperties = {
  width: "100%",
  "max-width": `${LEGACY_CONTENT_MAX_WIDTH}px`,
  margin: "0 auto",
};

export const contentInnerArtifactStyle: JSX.CSSProperties = {
  ...contentInnerStyle,
  height: "100%",
  "max-width": "none",
};
