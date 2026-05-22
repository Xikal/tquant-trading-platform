import { useCallback, useEffect, useRef } from "react";
import {
  selectActiveWorkspaceLoading,
  useWorkspaceLoadingStore,
} from "../../stores/workspaceLoadingStore";
import { errorMessage } from "../workspace-shared/workspaceFormatters";

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
  const loadingState = useWorkspaceLoadingStore((state) => state.loadingState);
  const loading = useWorkspaceLoadingStore(selectActiveWorkspaceLoading);
  const setLoadingKeyState = useWorkspaceLoadingStore((state) => state.setLoadingKey);
  const clearLoadingKeysState = useWorkspaceLoadingStore((state) => state.clearLoadingKeys);
  const onErrorRef = useRef(onError);
  const onAuthRequiredRef = useRef(onAuthRequired);

  useEffect(() => {
    onErrorRef.current = onError;
    onAuthRequiredRef.current = onAuthRequired;
  }, [onAuthRequired, onError]);

  const setLoadingKey = useCallback((key: string, active: boolean) => {
    setLoadingKeyState(key, active);
  }, [setLoadingKeyState]);

  const setPaperLoading = useCallback((key: string) => {
    if (!key) {
      clearLoadingKeysState(PAPER_LOADING_KEYS);
      return;
    }
    setLoadingKeyState(key, true);
  }, [clearLoadingKeysState, setLoadingKeyState]);

  const withLoading = useCallback(async <T,>(key: string, action: () => Promise<T>): Promise<T | undefined> => {
    try {
      setLoadingKey(key, true);
      onErrorRef.current("");
      return await action();
    } catch (err) {
      const message = errorMessage(err);
      onErrorRef.current(message);
      if (isAuthError(err, message)) {
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

function isAuthError(reason: unknown, message: string): boolean {
  const status = (reason as { status?: number } | null)?.status;
  if (status !== undefined) {
    return status === 401;
  }
  const normalized = message.toLowerCase();
  return (
    normalized.includes("401") ||
    normalized.includes("unauthorized") ||
    normalized.includes("not authenticated")
  );
}
