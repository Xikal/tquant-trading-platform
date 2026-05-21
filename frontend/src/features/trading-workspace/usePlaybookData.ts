import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { applyQuoteRefreshToResponse } from "../playbook/formatters";
import type { AuthUser, LowBuyScreenerResult } from "../../types";
import {
  DEFAULT_PLAYBOOK_STRATEGY,
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

export function usePlaybookData({
  currentUser,
  page,
  withLoading,
}: {
  currentUser: AuthUser | null;
  page: Page;
  withLoading: WorkspaceLoader;
}) {
  const [strategy, setStrategyState] = useState(DEFAULT_PLAYBOOK_STRATEGY);
  const [playbook, setPlaybook] = useState<LowBuyScreenerResult | null>(null);
  const cacheRef = useRef<Record<string, LowBuyScreenerResult>>({});
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
      const cached = cacheRef.current[nextStrategy];
      if (cached && !force) {
        setPlaybook(cached);
        return cached;
      }
      return await withLoadingRef.current("playbook", async () => {
        const requestId = ++requestRef.current;
        const result = await api.getLowBuyCandidates(nextStrategy, 18, 480, false, "full");
        if (requestId === requestRef.current) {
          setPlaybook(result);
          cacheRef.current = { ...cacheRef.current, [nextStrategy]: result };
        }
        return result;
      });
    },
    [],
  );

  const setStrategy = useCallback(
    (nextStrategy: string) => {
      setStrategyState(nextStrategy);
      setPlaybook(cacheRef.current[nextStrategy] ?? null);
    },
    [],
  );

  const resetPlaybook = useCallback(() => {
    setPlaybook(null);
    cacheRef.current = {};
  }, []);

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
