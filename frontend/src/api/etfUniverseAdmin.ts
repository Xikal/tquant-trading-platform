import { invalidateCache } from "./base";
import { apiClient } from "./httpClient";
import type {
  EtfUniverseAdminResponse,
  EtfUniverseApplyRequest,
  EtfUniverseMutationResponse,
  EtfUniverseOverrideMap,
  EtfUniverseRepairDraftResponse,
  EtfUniverseRollbackRequest,
} from "../types/etfUniverseAdmin";

const request = apiClient.request;

export const etfUniverseAdminApi = {
  getAdmin: () => request<EtfUniverseAdminResponse>("/market/etf-universe/admin"),

  validate: (draft_overrides: EtfUniverseOverrideMap) =>
    request<EtfUniverseAdminResponse>("/market/etf-universe/validate", {
      method: "POST",
      body: JSON.stringify({ draft_overrides }),
    }),

  repairDraft: (payload: { symbol: string; name?: string; category?: string }) =>
    request<EtfUniverseRepairDraftResponse>("/market/etf-universe/repair-draft", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  apply: (payload: EtfUniverseApplyRequest) =>
    request<EtfUniverseMutationResponse>("/market/etf-universe/apply", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => {
      invalidateCache(["/market/etf-universe", "/market/sector-etf-t0"]);
      return result;
    }),

  rollback: (payload: EtfUniverseRollbackRequest) =>
    request<EtfUniverseMutationResponse>("/market/etf-universe/rollback", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => {
      invalidateCache(["/market/etf-universe", "/market/sector-etf-t0"]);
      return result;
    }),
};
