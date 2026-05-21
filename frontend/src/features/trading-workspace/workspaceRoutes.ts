import { PATH_PAGE_MAP } from "../workspace-shared/workspaceConstants";
import type { Page } from "../workspace-shared/workspaceTypes";

export function pageFromLocation(): Page {
  if (typeof window === "undefined") {
    return "monitor";
  }
  return PATH_PAGE_MAP[window.location.pathname] ?? "monitor";
}

export function normalizeLegacyWorkspacePath(): boolean {
  // Deprecated workspace routes are now handled by the backend.  The SPA no
  // longer rewrites them silently.
  return false;
}
