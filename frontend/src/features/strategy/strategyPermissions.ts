import type { AuthUser } from "../../types";

export function isAdmin(user: AuthUser): boolean {
  const roles = userRoles(user);
  return roles.has("admin") || roles.has("administrator");
}

export function canOptimize(user: AuthUser): boolean {
  return isAdmin(user) || userRoles(user).has("backtest_optimizer");
}

export function canValidate(user: AuthUser): boolean {
  const roles = userRoles(user);
  return isAdmin(user) || roles.has("backtest_optimizer") || roles.has("backtest_research");
}

function userRoles(user: AuthUser): Set<string> {
  return new Set((user.roles ?? []).map((role) => role.trim().toLowerCase()).filter(Boolean));
}
