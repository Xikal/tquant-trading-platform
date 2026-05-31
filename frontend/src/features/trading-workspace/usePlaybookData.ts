import { useCallback, useEffect, useMemo, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { applyQuoteRefreshToResponse } from "../playbook/formatters";
import type { AuthUser, LowBuyScreenerResult } from "../../types";
import { useWorkspacePlaybookStore } from "../../stores/workspacePlaybookStore";
import { useServerState } from "../../state/serverState";
import {
  PLAYBOOK_QUOTE_REFRESH_LIMIT,
} from "../workspace-shared/workspaceConstants";
import type { Page } from "../workspace-shared/workspaceTypes";
import { trackedPlaybookSymbols } from "../workspace-shared/workspaceViewModels";
import {
  realtimePriceRefreshIntervalMs,
  refreshTradingSessionStatus,
  shouldRefreshRealtimePrices,
} from "./realtimePriceRefresh";

type WorkspaceLoader = <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;

function playbookServerKey(strategy: string) {
  return ["workspace-playbook", strategy] as const;
}

export function usePlaybookData({
  currentUser,
  page,
  withLoading,
}: {
  currentUser: AuthUser | null;
  page: Page;
  withLoading: WorkspaceLoader;
}) {
  const queryClient = useQueryClient();
  const strategy = useWorkspacePlaybookStore((state) => state.strategy);
  const setStrategyState = useWorkspacePlaybookStore((state) => state.setStrategy);
  const resetPlaybookState = useWorkspacePlaybookStore((state) => state.resetPlaybook);
  const currentPlaybookKey = useMemo(() => playbookServerKey(strategy), [strategy]);
  const [playbook, setPlaybook, resetPlaybookQuery] = useServerState<LowBuyScreenerResult | null>(currentPlaybookKey, null);
  const requestRef = useRef(0);
  const withLoadingRef = useRef(withLoading);
  const playbookRef = useRef<LowBuyScreenerResult | null>(null);

  useEffect(() => {
    withLoadingRef.current = withLoading;
  }, [withLoading]);

  useEffect(() => {
    playbookRef.current = playbook;
  }, [playbook]);

  const loadPlaybook = useCallback(
    async (nextStrategy: string, force = false) => {
      const key = playbookServerKey(nextStrategy);
      const cached = queryClient.getQueryData<LowBuyScreenerResult | null>(key);
      if (cached && !force) {
        return cached;
      }
      return await withLoadingRef.current("playbook", async () => {
        const requestId = ++requestRef.current;
        const result = await api.getLowBuyCandidates(nextStrategy, 18, 480, false, "full");
        if (requestId === requestRef.current) {
          queryClient.setQueryData(key, result);
        }
        return result;
      });
    },
    [queryClient],
  );

  const setStrategy = useCallback(
    (nextStrategy: string) => {
      setStrategyState(nextStrategy);
    },
    [setStrategyState],
  );

  const resetPlaybook = useCallback(() => {
    resetPlaybookState();
    resetPlaybookQuery();
  }, [resetPlaybookQuery, resetPlaybookState]);

  useEffect(() => {
    if (currentUser && page === "playbook") {
      void loadPlaybook(strategy);
    }
  }, [currentUser, page, strategy, loadPlaybook]);

  useEffect(() => {
    if (!currentUser || page !== "playbook") {
      return undefined;
    }
    let active = true;
    let refreshing = false;
    async function refreshPlaybookQuotes() {
      if (!shouldRefreshRealtimePrices() || refreshing) {
        return;
      }
      const currentPlaybook = playbookRef.current;
      const symbols = currentPlaybook
        ? trackedPlaybookSymbols(currentPlaybook).slice(0, PLAYBOOK_QUOTE_REFRESH_LIMIT)
        : [];
      if (!symbols.length) {
        return;
      }
      refreshing = true;
      try {
        const result = await api.getLowBuyQuoteRefresh(strategy, symbols);
        if (active) {
          setPlaybook((current) =>
            current ? applyQuoteRefreshToResponse(current, result.items) : current
          );
        }
      } catch (err) {
        if (import.meta.env.DEV) {
          console.warn("低吸实时价格刷新失败，已保留上次结果。", err);
        }
      } finally {
        refreshing = false;
      }
    }
    let timer: number | undefined;
    const scheduleNext = () => {
      void refreshTradingSessionStatus(api.getMarketTradingSession).finally(() => {
        if (!active) {
          return;
        }
        timer = window.setTimeout(() => {
          void refreshPlaybookQuotes().finally(() => {
            if (active) {
              scheduleNext();
            }
          });
        }, realtimePriceRefreshIntervalMs());
      });
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void refreshPlaybookQuotes();
      }
    };
    void refreshTradingSessionStatus(api.getMarketTradingSession).finally(() => {
      if (active) {
        void refreshPlaybookQuotes();
        scheduleNext();
      }
    });
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      active = false;
      if (timer) {
        window.clearTimeout(timer);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [
    currentUser,
    page,
    strategy,
    playbook?.strategy_key,
  ]);

  return {
    strategy,
    playbook,
    loadPlaybook,
    resetPlaybook,
    setStrategy,
  };
}
