import { QueryClient, type QueryClientConfig } from "@tanstack/react-query";

export const queryClientDefaults = {
  staleTime: 15_000,
  gcTime: 5 * 60_000,
  refetchOnWindowFocus: false,
  retry: false,
  structuralSharing: true,
} as const;

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

export const queryClient = createAppQueryClient();
