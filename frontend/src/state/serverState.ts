import { useCallback } from "react";
import { useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";

export type ServerStateValue<T> = T | ((current: T) => T);

export function useServerState<T>(queryKey: QueryKey, initialData: T) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey,
    queryFn: async () => queryClient.getQueryData<T>(queryKey) ?? initialData,
    initialData,
    staleTime: Number.POSITIVE_INFINITY,
    gcTime: Number.POSITIVE_INFINITY,
  });
  const setValue = useCallback((value: ServerStateValue<T>) => {
    queryClient.setQueryData<T>(queryKey, (current) => (
      typeof value === "function"
        ? (value as (current: T) => T)(current ?? initialData)
        : value
    ));
  }, [initialData, queryClient, queryKey]);
  const resetValue = useCallback(() => {
    queryClient.setQueryData<T>(queryKey, initialData);
  }, [initialData, queryClient, queryKey]);
  return [query.data ?? initialData, setValue, resetValue] as const;
}
