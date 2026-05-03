export type LoadingState = Record<string, boolean>;

export function activeLoadingKey(state: LoadingState): string {
  return Object.keys(state).find((key) => state[key]) ?? "";
}

export function isLoading(state: LoadingState, key: string): boolean {
  return Boolean(state[key]);
}

export function setLoadingFlag(state: LoadingState, key: string, active: boolean): LoadingState {
  if (!key) {
    return state;
  }
  const next = { ...state };
  if (active) {
    next[key] = true;
  } else {
    delete next[key];
  }
  return next;
}

export function clearLoadingKeys(state: LoadingState, keys: string[]): LoadingState {
  const next = { ...state };
  for (const key of keys) {
    delete next[key];
  }
  return next;
}
