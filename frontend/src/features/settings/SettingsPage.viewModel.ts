import type {
  AuthUser,
  FactorWeightsResponse,
  SettingsPayload,
  UserSectorExclusionsResponse,
} from "../../types";
import type { SettingsDraft } from "../workspace-shared/workspaceTypes";
import type { SettingsTabItem } from "./SettingsPageTabs";
import { buildSettingsDirtyState, sameStringSet } from "./SettingsPage.helpers";

export interface SettingsPageViewModelInput {
  currentUser: AuthUser;
  settings: SettingsPayload | null;
  factorWeights: FactorWeightsResponse | null;
  draft: SettingsDraft;
  factorDraft: Record<string, string>;
  sectorDraft: string[];
  sectorQuery: string;
  sectorExclusions: UserSectorExclusionsResponse | null;
}

export interface SettingsPageViewModel {
  isAdmin: boolean;
  dirtyState: ReturnType<typeof buildSettingsDirtyState>;
  sectorDirty: boolean;
  visibleDirtyCount: number;
  unsavedCount: number;
  filteredSectors: string[];
  settingsTabs: SettingsTabItem[];
}

export function buildSettingsPageViewModel(input: SettingsPageViewModelInput): SettingsPageViewModel {
  const isAdmin = userIsAdmin(input.currentUser);
  const dirtyState = buildSettingsDirtyState(input.settings, input.factorWeights, input.draft, input.factorDraft);
  const sectorDirty = !sameStringSet(input.sectorDraft, input.sectorExclusions?.excluded_sectors ?? []);
  const visibleDirtyCount = Number(dirtyState.risk)
    + (isAdmin ? Number(dirtyState.llm) + Number(dirtyState.data) + Number(dirtyState.factor) : 0);
  const unsavedCount = visibleDirtyCount + (sectorDirty ? 1 : 0);
  const filteredSectors = filterSectors(input.sectorExclusions?.available_sectors ?? [], input.sectorQuery);
  return {
    isAdmin,
    dirtyState,
    sectorDirty,
    visibleDirtyCount,
    unsavedCount,
    filteredSectors,
    settingsTabs: buildSettingsTabs({ isAdmin, dirtyState, sectorDirty }),
  };
}

function userIsAdmin(user: AuthUser): boolean {
  return user.roles.some((role) => {
    const normalized = role.trim().toLowerCase();
    return normalized === "admin" || normalized === "administrator";
  });
}

function filterSectors(sectors: string[], sectorQuery: string): string[] {
  const query = sectorQuery.trim().toLowerCase();
  if (!query) return sectors;
  return sectors.filter((sector) => sector.toLowerCase().includes(query));
}

function buildSettingsTabs({
  isAdmin,
  dirtyState,
  sectorDirty,
}: {
  isAdmin: boolean;
  dirtyState: ReturnType<typeof buildSettingsDirtyState>;
  sectorDirty: boolean;
}): SettingsTabItem[] {
  const baseTabs: SettingsTabItem[] = [
    { key: "account", label: "账户与安全", description: "安全与权限" },
    { key: "trading", label: "交易偏好", description: "风控、行业、退出", dirty: dirtyState.risk || sectorDirty },
  ];
  if (!isAdmin) {
    return baseTabs;
  }
  return [
    ...baseTabs,
    { key: "llm", label: "模型与因子", description: "DeepSeek、权重、ML", dirty: dirtyState.llm || dirtyState.factor, admin: true },
    { key: "data", label: "数据与运行", description: "数据源、运行状态", dirty: dirtyState.data, admin: true },
    { key: "governance", label: "诊断与审计", description: "治理、开关、审计", admin: true },
  ];
}
