import { request as baseRequest, requestCached as baseRequestCached } from "./base";
import type { ApiRequestInit } from "./requestTypes";

export interface IApiClient {
  request<T>(path: string, init?: ApiRequestInit): Promise<T>;
  requestCached<T>(path: string, ttlMs: number, init?: ApiRequestInit): Promise<T>;
}

const defaultClient: IApiClient = {
  request: baseRequest,
  requestCached: baseRequestCached,
};
let currentClient: IApiClient = defaultClient;

export function configureApiClient(client: IApiClient) {
  currentClient = client;
}

export function resetApiClient() {
  currentClient = defaultClient;
}

export const apiClient: IApiClient = {
  request: (path, init) => currentClient.request(path, init),
  requestCached: (path, ttlMs, init) => currentClient.requestCached(path, ttlMs, init),
};
