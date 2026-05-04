import { useCallback, useEffect, useRef, useState } from "react";
import { activeLoadingKey, clearLoadingKeys, setLoadingFlag, type LoadingState } from "./loadingState";
import { errorMessage } from "./workspaceFormatters";

const PAPER_LOADING_KEYS = [
  "paper",
  "paper-refresh",
  "paper-quotes",
  "paper-status",
  "paper-order",
  "paper-tags",
];

export function useWorkspaceLoading({
  onError,
  onAuthRequired,
}: {
  onError: (message: string) => void;
  onAuthRequired: () => void;
}) {
  const [loadingState, setLoadingState] = useState<LoadingState>({});
  const loading = activeLoadingKey(loadingState);
  const onErrorRef = useRef(onError);
  const onAuthRequiredRef = useRef(onAuthRequired);

  useEffect(() => {
    onErrorRef.current = onError;
    onAuthRequiredRef.current = onAuthRequired;
  }, [onAuthRequired, onError]);

  const setLoadingKey = useCallback((key: string, active: boolean) => {
    setLoadingState((current) => setLoadingFlag(current, key, active));
  }, []);

  const setPaperLoading = useCallback((key: string) => {
    setLoadingState((current) => {
      if (!key) {
        return clearLoadingKeys(current, PAPER_LOADING_KEYS);
      }
      return setLoadingFlag(current, key, true);
    });
  }, []);

  const withLoading = useCallback(async <T,>(key: string, action: () => Promise<T>): Promise<T | undefined> => {
    try {
      setLoadingKey(key, true);
      onErrorRef.current("");
      return await action();
    } catch (err) {
      const message = errorMessage(err);
      onErrorRef.current(message);
      if (isAuthErrorMessage(message)) {
        onAuthRequiredRef.current();
      }
      return undefined;
    } finally {
      setLoadingKey(key, false);
    }
  }, [setLoadingKey]);

  return {
    loading,
    loadingState,
    setLoadingKey,
    setPaperLoading,
    withLoading,
  };
}

function isAuthErrorMessage(message: string): boolean {
  const normalized = message.toLowerCase();
  return (
    normalized.includes("401") ||
    normalized.includes("unauthorized") ||
    normalized.includes("not authenticated") ||
    message.includes("登录") ||
    message.includes("账号未开通")
  );
}
