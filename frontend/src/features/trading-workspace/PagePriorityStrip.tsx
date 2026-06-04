import type { Page } from "../workspace-shared/workspaceTypes";
import { ModeSafetyBadges } from "../../ui/feedback/ModeSafetyBadges";
import { pageResponsibility } from "./pageResponsibilities";

export function PagePriorityStrip({ page }: { page: Page }) {
  const responsibility = pageResponsibility(page);
  if (!responsibility) return null;

  return (
    <div className="workspace-priority-strip" data-testid="workspace-priority-strip">
      <div className="workspace-priority-strip__lead">
        <span>{responsibility.label}</span>
        <strong>{responsibility.coreQuestion}</strong>
      </div>
      <div className="workspace-priority-strip__items" aria-label={`${responsibility.label}信息层级`}>
        <span>首屏：{responsibility.primarySections.join(" / ")}</span>
        <span>明细：{responsibility.detailSections.join(" / ")}</span>
        <span>模式：{responsibility.drilldownPattern}</span>
        <ModeSafetyBadges kinds={[...responsibility.modeBadges]} />
      </div>
    </div>
  );
}
