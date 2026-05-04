import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { applyQuoteRefreshToResponse } from "../playbook/formatters";
import type { AuthUser, LowBuyScreenerResult } from "../../types";
import {
  DEFAULT_PLAYBOOK_STRATEGY,
  PLAYBOOK_QUOTE_REFRESH_INTERVAL_MS,
  PLAYBOOK_QUOTE_REFRESH_LIMIT,
} from "./workspaceConstants";
import type { Page } from "./workspaceTypes";
import { trackedPlaybookSymbols } from "./workspaceViewModels";

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

  const loadPlaybook = useCallback(
    async (nextStrategy: string, force = false) => {
      const cached = cacheRef.current[nextStrategy];
      if (cached && !force) {
        setPlaybook(cached);
        return cached;
      }
      return await withLoading("playbook", async () => {
        const requestId = ++requestRef.current;
        const result = await api.getLowBuyCandidates(nextStrategy, 18, 480, false, "full");
        if (requestId === requestRef.current) {
          setPlaybook(result);
          cacheRef.current = { ...cacheRef.current, [nextStrategy]: result };
        }
        return result;
      });
    },
    [withLoading],
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
    if (!currentUser || page !== "playbook" || !playbook) {
      return undefined;
    }
    const currentPlaybook = playbook;
    let active = true;
    let refreshing = false;
    async function refreshPlaybookQuotes() {
      if (refreshing) {
        return;
      }
      const symbols = trackedPlaybookSymbols(currentPlaybook).slice(0, PLAYBOOK_QUOTE_REFRESH_LIMIT);
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
    const timer = window.setInterval(() => {
      void refreshPlaybookQuotes();
    }, PLAYBOOK_QUOTE_REFRESH_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [
    currentUser,
    page,
    strategy,
    playbook?.latest_trade_date,
    playbook?.strategy_key,
    playbook?.confirmed_candidates.length,
    playbook?.candidates.length,
  ]);

  return {
    strategy,
    playbook,
    loadPlaybook,
    resetPlaybook,
    setStrategy,
  };
}
