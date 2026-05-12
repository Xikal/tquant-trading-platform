import { apiClient } from "./httpClient";

export interface OperationAuditItem {
  id: number;
  user_id?: number | null;
  operation: string;
  resource_type: string;
  resource_id: string;
  status: string;
  operator_ip: string;
  created_at: string;
}

export interface OperationAuditResponse {
  items: OperationAuditItem[];
  total: number;
  limit: number;
  offset: number;
}

export const operationAuditApi = {
  list: (limit = 20) => apiClient.request<OperationAuditResponse>(`/operation-audit?limit=${limit}`),
};
