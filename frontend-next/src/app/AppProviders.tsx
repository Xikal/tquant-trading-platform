import type { JSX } from "solid-js";
import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";
import { AuthProvider } from "../features/auth/authModel";
import { ApiError, ApiTransportError } from "../shared/api/errors";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: false,
      retry: (_failureCount, error) => shouldRetryQuery(error),
    },
  },
});

export function AppProviders(props: { children: JSX.Element }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{props.children}</AuthProvider>
    </QueryClientProvider>
  );
}

function shouldRetryQuery(error: unknown): boolean {
  if (error instanceof ApiError) return false;
  if (error instanceof ApiTransportError) return false;
  return false;
}
