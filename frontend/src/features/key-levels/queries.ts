import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { featureFlagsApi } from "../../api/featureFlags";

const A_KEY_LEVEL_FLAG = "a_key_level_engine_enabled";

export function useAKeyLevelFeatureEnabled() {
  return useQuery({
    queryKey: ["feature-flags", A_KEY_LEVEL_FLAG],
    queryFn: async () => {
      const payload = await featureFlagsApi.list();
      const item = payload.flags?.[A_KEY_LEVEL_FLAG] ?? payload.items?.find((flag) => flag.key === A_KEY_LEVEL_FLAG);
      return Boolean(item?.enabled);
    },
    staleTime: 60_000,
  });
}

export function useStockKeyLevels(symbol?: string | null, includeIntraday = false) {
  const normalized = symbol?.trim() ?? "";
  const feature = useAKeyLevelFeatureEnabled();
  return useQuery({
    queryKey: ["key-levels", "stock", normalized, includeIntraday],
    queryFn: () => api.getStockKeyLevels(normalized, includeIntraday),
    enabled: feature.data === true && Boolean(normalized),
    staleTime: 20_000,
  });
}

export function useMarketKeyLevels() {
  const feature = useAKeyLevelFeatureEnabled();
  return useQuery({
    queryKey: ["key-levels", "market"],
    queryFn: () => api.getMarketKeyLevels(),
    enabled: feature.data === true,
    staleTime: 30_000,
  });
}

export function useSectorKeyLevels(sectorKey?: string | null) {
  const normalized = sectorKey?.trim() ?? "";
  const feature = useAKeyLevelFeatureEnabled();
  return useQuery({
    queryKey: ["key-levels", "sector", normalized],
    queryFn: () => api.getSectorKeyLevels(normalized),
    enabled: feature.data === true && Boolean(normalized),
    staleTime: 30_000,
  });
}
