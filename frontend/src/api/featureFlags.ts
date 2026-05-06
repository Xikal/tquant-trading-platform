import { request } from "./base";

export interface FeatureFlagItem {
  key: string;
  enabled: boolean;
  default: boolean;
  type: string;
  description: string;
  source: string;
}

export const featureFlagsApi = {
  list: () => request<{ items: FeatureFlagItem[] }>("/settings/feature-flags"),
  update: (key: string, enabled: boolean) =>
    request<{ ok: boolean; item: FeatureFlagItem }>(`/settings/feature-flags/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ enabled }),
    }),
};
