import { useCallback, useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { PAGE_PATHS } from "../workspace-shared/workspaceConstants";
import { pageFromPath } from "./workspaceRoutes";
import type { Page } from "../workspace-shared/workspaceTypes";
import { useWorkspaceStore } from "../../stores/workspaceStore";

export function useWorkspaceNavigation() {
  const location = useLocation();
  const routerNavigate = useNavigate();
  const page = useWorkspaceStore((state) => state.page);
  const setPage = useWorkspaceStore((state) => state.setPage);

  useEffect(() => {
    setPage(pageFromPath(location.pathname));
  }, [location.pathname, setPage]);

  const navigatePage = useCallback((nextPage: Page) => {
    setPage(nextPage);
    const nextPath = PAGE_PATHS[nextPage];
    if (location.pathname !== nextPath) {
      routerNavigate(nextPath);
    }
  }, [location.pathname, routerNavigate, setPage]);

  return { page, navigatePage };
}
