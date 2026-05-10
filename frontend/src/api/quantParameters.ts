import { request } from "./base";

export interface QuantParameterSet {
  id: number;
  version: string;
  name: string;
  scope: string;
  status: string;
  params: Record<string, unknown>;
  description: string;
  created_by: string;
  created_at: string;
  activated_at?: string | null;
}

export interface QuantParameterCreatePayload {
  version: string;
  name?: string;
  scope?: string;
  params: Record<string, unknown>;
  description?: string;
  activate?: boolean;
}

export const quantParametersApi = {
  current: (scope = "global") => request<QuantParameterSet>(`/quant/parameters/current?scope=${encodeURIComponent(scope)}`),
  schema: () => request<Record<string, unknown>>("/quant/parameters/schema"),
  create: (payload: QuantParameterCreatePayload) =>
    request<QuantParameterSet>("/quant/parameters", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
