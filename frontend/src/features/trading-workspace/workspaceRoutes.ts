import { PATH_PAGE_MAP } from "../workspace-shared/workspaceConstants";
import type { Page } from "../workspace-shared/workspaceTypes";

export function pageFromPath(pathname: string): Page {
  return PATH_PAGE_MAP[pathname] ?? "monitor";
}
