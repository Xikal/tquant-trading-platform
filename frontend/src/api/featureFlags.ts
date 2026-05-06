import { request } from "./base";

export interface FeatureFlagItem {
  key: string;
  enabled: boolean;
  value?: boolean;
  default: boolean;
  type: string;
  description: string;
  source: string;
  updated_at?: string;
  updated_by?: string;
}

export interface FeatureFlagAuditItem {
  id: number;
  flag_key: string;
  old_value: string;
  new_value: string;
  operator_user_id?: number | null;
  operator_ip?: string;
  created_at: string;
}

export const featureFlagsApi = {
  list: () => request<{ items: FeatureFlagItem[]; flags?: Record<string, FeatureFlagItem>; updated_at?: string }>("/settings/feature-flags"),
  audit: () => request<{ items: FeatureFlagAuditItem[] }>("/settings/feature-flags/audit"),
  update: (key: string, enabled: boolean) =>
    request<{ ok: boolean; item: FeatureFlagItem; flag?: FeatureFlagItem }>(`/settings/feature-flags/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ enabled }),
    }),
};
