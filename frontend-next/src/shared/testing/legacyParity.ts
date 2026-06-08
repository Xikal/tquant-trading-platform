import { nextRoutes } from "../config/routes";

export const parityMatrix = nextRoutes.map((route) => ({
  currentRoute: route.legacyPath,
  nextRoute: route.path,
  status: "shadow-ready",
  gate: "style-spec + API contract smoke + screenshot parity",
}));

export function routeHasParityTarget(path: string): boolean {
  return parityMatrix.some((item) => item.nextRoute === path || item.currentRoute === path);
}
