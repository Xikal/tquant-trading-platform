import { create } from "zustand";
import { DEFAULT_PLAYBOOK_STRATEGY } from "../features/workspace-shared/workspaceConstants";

interface WorkspacePlaybookStore {
  strategy: string;
  setStrategy: (strategy: string) => void;
  resetPlaybook: () => void;
}

export const useWorkspacePlaybookStore = create<WorkspacePlaybookStore>((set) => ({
  strategy: DEFAULT_PLAYBOOK_STRATEGY,
  setStrategy: (strategy) => set({ strategy }),
  resetPlaybook: () => set({ strategy: DEFAULT_PLAYBOOK_STRATEGY }),
}));
