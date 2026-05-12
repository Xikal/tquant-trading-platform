import { useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, getAuthAccessToken, request } from "../../api/base";
import type { AuthUser, IntradayConfirmationItem, PaperPosition } from "../../types";
import type { Page } from "./workspaceTypes";

export function usePaperIntraday({
  currentUser,
  page,
  positions,
  refreshAutoTradingStatus,
}: {
  currentUser: AuthUser | null;
  page: Page;
  positions: PaperPosition[];
  refreshAutoTradingStatus: () => Promise<void>;
}) {
  const [intradayConfirmations, setIntradayConfirmations] = useState<IntradayConfirmationItem[]>([]);
  const refreshAutoTradingStatusRef = useRef(refreshAutoTradingStatus);
  const positionSymbols = useMemo(
    () => positions.map((item) => item.symbol).filter(Boolean).slice(0, 12).join(","),
    [positions],
  );

  useEffect(() => {
    refreshAutoTradingStatusRef.current = refreshAutoTradingStatus;
  }, [refreshAutoTradingStatus]);

  useEffect(() => {
    let source: EventSource | undefined;
    let cancelled = false;
    let lastEventId = "";
    if (!currentUser || page !== "paper" || !positionSymbols) {
      setIntradayConfirmations([]);
      return undefined;
    }
    if (!getAuthAccessToken()) {
      setIntradayConfirmations([]);
      return undefined;
    }
    void request<{ stream_token: string; expires_in: number }>("/intraday/subscribe", { method: "POST" })
      .then((payload) => {
        if (cancelled || !payload.stream_token) {
          return;
        }
        const normalizedBase = API_BASE.replace(/\/$/, "");
        const agentBase = normalizedBase.endsWith("/api") ? normalizedBase : `${normalizedBase}/api`;
        const buildUrl = () => `${agentBase}/intraday/stream?symbols=${encodeURIComponent(positionSymbols)}&client_id=web-paper&stream_token=${encodeURIComponent(payload.stream_token)}&interval_seconds=20&last_event_id=${encodeURIComponent(lastEventId)}`;
        const url = buildUrl();
        source = new EventSource(url);
        source.addEventListener("intraday_confirmations", (event) => {
          try {
            lastEventId = (event as MessageEvent).lastEventId || lastEventId;
            const payload = JSON.parse((event as MessageEvent).data) as { items?: IntradayConfirmationItem[] };
            setIntradayConfirmations(payload.items ?? []);
          } catch {
            setIntradayConfirmations([]);
          }
        });
        source.onerror = () => {
          source?.close();
        };
      })
      .catch(() => setIntradayConfirmations([]));
    return () => {
      cancelled = true;
      source?.close();
    };
  }, [currentUser, page, positionSymbols]);

  useEffect(() => {
    if (!currentUser || page !== "paper" || !currentUser.can_paper_trade) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void refreshAutoTradingStatusRef.current();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [currentUser, page, currentUser?.can_paper_trade]);

  return intradayConfirmations;
}
