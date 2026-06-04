import { describe, expect, it } from "vitest";
import {
  createAppQueryClient,
  isRetryableQueryError,
  queryClientDefaults,
  retryQuery,
  retryQueryDelay,
} from "./queryClient";

describe("createAppQueryClient", () => {
  it("uses the shared frontend server-state defaults", () => {
    const client = createAppQueryClient();
    const options = client.getDefaultOptions();

    expect(options.queries?.refetchOnWindowFocus).toBe(false);
    expect(options.queries?.refetchOnMount).toBe(false);
    expect(options.queries?.refetchOnReconnect).toBe(true);
    expect(options.queries?.staleTime).toBe(queryClientDefaults.staleTime);
    expect(options.queries?.gcTime).toBe(queryClientDefaults.gcTime);
    expect(options.queries?.structuralSharing).toBe(true);
    expect(options.queries?.retry).toBe(retryQuery);
    expect(options.queries?.retryDelay).toBe(retryQueryDelay);
    expect(typeof options.queries?.placeholderData).toBe("function");
    expect(options.mutations?.retry).toBe(false);
  });
});

describe("query retry policy", () => {
  it("retries only transient network, timeout, and 5xx query failures twice", () => {
    expect(retryQuery(0, new Error("Failed to fetch"))).toBe(true);
    expect(retryQuery(1, httpError(503))).toBe(true);
    expect(retryQuery(1, httpError(500))).toBe(true);
    expect(retryQuery(1, httpError(408))).toBe(true);
    expect(retryQuery(1, new Error("请求超过 8 秒未响应，请稍后重试"))).toBe(true);
    expect(retryQuery(2, httpError(503))).toBe(false);
  });

  it("does not retry auth, client, not-found, validation, or abort failures", () => {
    for (const status of [400, 401, 403, 404, 422]) {
      expect(isRetryableQueryError(httpError(status))).toBe(false);
      expect(retryQuery(0, httpError(status))).toBe(false);
    }
    expect(retryQuery(0, new DOMException("aborted", "AbortError"))).toBe(false);
    expect(retryQuery(0, new Error("请求已取消，请重试"))).toBe(false);
  });

  it("uses capped exponential retry delay", () => {
    expect(retryQueryDelay(0)).toBe(1000);
    expect(retryQueryDelay(1)).toBe(2000);
    expect(retryQueryDelay(3)).toBe(8000);
    expect(retryQueryDelay(10)).toBe(8000);
  });
});

function httpError(status: number): Error & { status: number } {
  const error = new Error(`Request failed: ${status}`) as Error & { status: number };
  error.status = status;
  return error;
}
