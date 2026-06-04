import { QueryClient, type QueryClientConfig } from "@tanstack/react-query";

export function isRetryableQueryError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return true;
  }
  if (error.name === "AbortError") {
    return false;
  }
  const message = error.message.toLowerCase();
  if (message.includes("abort") || message.includes("取消")) {
    return false;
  }
  const status = (error as Error & { status?: number }).status;
  if (status === undefined) {
    return true;
  }
  if (status === 408 || status === 429) {
    return true;
  }
  return status >= 500;
}

export function retryQuery(failureCount: number, error: unknown): boolean {
  return failureCount < 2 && isRetryableQueryError(error);
}

export function retryQueryDelay(attemptIndex: number): number {
  return Math.min(1000 * 2 ** attemptIndex, 8000);
}

export const queryClientDefaults = {
  staleTime: 15_000,
  gcTime: 5 * 60_000,
  placeholderData: <T>(previousData: T | undefined) => previousData,
  refetchOnMount: false,
  refetchOnReconnect: true,
  refetchOnWindowFocus: false,
  retry: retryQuery,
  retryDelay: retryQueryDelay,
  structuralSharing: true,
} as const;

const queryClientDefaultOptions = {
  queries: queryClientDefaults,
  mutations: {
    retry: false,
  },
} satisfies QueryClientConfig["defaultOptions"];

export const queryClient = new QueryClient({
  defaultOptions: queryClientDefaultOptions,
});

export function createAppQueryClient(config: QueryClientConfig = {}) {
  return new QueryClient({
    ...config,
    defaultOptions: {
      ...config.defaultOptions,
      queries: {
        ...queryClientDefaults,
        ...config.defaultOptions?.queries,
      },
      mutations: {
        retry: false,
        ...config.defaultOptions?.mutations,
      },
    },
  });
}
