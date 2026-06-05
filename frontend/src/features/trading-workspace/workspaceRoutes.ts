import { PATH_PAGE_MAP } from "../workspace-shared/workspaceConstants";
import type { Page } from "../workspace-shared/workspaceTypes";

type MonitorDataPage = Extract<Page, "monitor" | "monitor-market">;

export function pageFromPath(pathname: string): Page {
  return PATH_PAGE_MAP[pathname] ?? "monitor";
}

export function isMonitorDataPage(page: Page): page is MonitorDataPage {
  return page === "monitor" || page === "monitor-market";
}
