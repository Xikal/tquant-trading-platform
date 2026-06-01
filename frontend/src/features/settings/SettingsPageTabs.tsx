export type SettingsTabKey = "account" | "trading" | "llm" | "data" | "governance";

export interface SettingsTabItem {
  admin?: boolean;
  key: SettingsTabKey;
  label: string;
  description: string;
  dirty?: boolean;
}
