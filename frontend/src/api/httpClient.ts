import { request as baseRequest, requestCached as baseRequestCached } from "./base";
import type { ApiRequestInit } from "./requestTypes";

export interface IApiClient {
  request<T>(path: string, init?: ApiRequestInit): Promise<T>;
  requestCached<T>(path: string, ttlMs: number, init?: ApiRequestInit): Promise<T>;
}

class DefaultApiClient implements IApiClient {
  request<T>(path: string, init?: ApiRequestInit): Promise<T> {
    return baseRequest<T>(path, init);
  }

  requestCached<T>(path: string, ttlMs: number, init?: ApiRequestInit): Promise<T> {
    return baseRequestCached<T>(path, ttlMs, init);
  }
}

const defaultClient: IApiClient = new DefaultApiClient();
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
