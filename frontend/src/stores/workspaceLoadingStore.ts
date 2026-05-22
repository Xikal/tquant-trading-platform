import { create } from "zustand";
import { activeLoadingKey, clearLoadingKeys, setLoadingFlag, type LoadingState } from "../features/trading-workspace/loadingState";

interface WorkspaceLoadingStore {
  loadingState: LoadingState;
  setLoadingKey: (key: string, active: boolean) => void;
  clearLoadingKeys: (keys: string[]) => void;
}

export const useWorkspaceLoadingStore = create<WorkspaceLoadingStore>((set) => ({
  loadingState: {},
  setLoadingKey: (key, active) => set((state) => ({
    loadingState: setLoadingFlag(state.loadingState, key, active),
  })),
  clearLoadingKeys: (keys) => set((state) => ({
    loadingState: clearLoadingKeys(state.loadingState, keys),
  })),
}));

export function selectActiveWorkspaceLoading(state: WorkspaceLoadingStore): string {
  return activeLoadingKey(state.loadingState);
}
