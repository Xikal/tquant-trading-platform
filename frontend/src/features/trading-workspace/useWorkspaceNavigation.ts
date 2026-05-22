import { useCallback, useEffect } from "react";
import { PAGE_PATHS } from "../workspace-shared/workspaceConstants";
import { normalizeLegacyWorkspacePath, pageFromLocation } from "./workspaceRoutes";
import type { Page } from "../workspace-shared/workspaceTypes";
import { useWorkspaceStore } from "../../stores/workspaceStore";

export function useWorkspaceNavigation() {
  const page = useWorkspaceStore((state) => state.page);
  const setPage = useWorkspaceStore((state) => state.setPage);

  useEffect(() => {
    normalizeLegacyWorkspacePath();
    setPage(pageFromLocation());
    function handlePopState() {
      normalizeLegacyWorkspacePath();
      setPage(pageFromLocation());
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [setPage]);

  const navigatePage = useCallback((nextPage: Page) => {
    setPage(nextPage);
    if (typeof window === "undefined") {
      return;
    }
    const nextPath = PAGE_PATHS[nextPage];
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
  }, []);

  return { page, navigatePage };
}
