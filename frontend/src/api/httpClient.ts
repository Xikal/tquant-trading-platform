import { request as baseRequest, requestCached as baseRequestCached } from "./base";

export interface IApiClient {
  request<T>(path: string, init?: RequestInit): Promise<T>;
  requestCached<T>(path: string, ttlMs: number, init?: RequestInit): Promise<T>;
}

class DefaultApiClient implements IApiClient {
  request<T>(path: string, init?: RequestInit): Promise<T> {
    return baseRequest<T>(path, init);
  }

  requestCached<T>(path: string, ttlMs: number, init?: RequestInit): Promise<T> {
    return baseRequestCached<T>(path, ttlMs, init);
  }
}

let currentClient: IApiClient = new DefaultApiClient();

export function configureApiClient(client: IApiClient) {
  currentClient = client;
}

export const apiClient: IApiClient = {
  request: (path, init) => currentClient.request(path, init),
  requestCached: (path, ttlMs, init) => currentClient.requestCached(path, ttlMs, init),
};
