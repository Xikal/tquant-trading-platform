import { useCallback, useEffect, useState } from "react";
import { PAGE_PATHS } from "./workspaceConstants";
import { pageFromLocation } from "./workspaceRoutes";
import type { Page } from "./workspaceTypes";

export function useWorkspaceNavigation() {
  const [page, setPage] = useState<Page>(() => pageFromLocation());

  useEffect(() => {
    function handlePopState() {
      setPage(pageFromLocation());
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

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
