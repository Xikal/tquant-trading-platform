import { normalizeApiBaseUrl } from "../../shared/api/runtimeBaseUrl";

export type DesktopCommand = "open_log_dir" | "open_data_dir";

export interface DesktopConfig {
  apiBaseUrl: string;
}

export interface TauriLike {
  core?: {
    invoke?: (name: string, args?: Record<string, unknown>) => Promise<unknown>;
  };
}

export function getTauri(): TauriLike | null {
  return (globalThis as { __TAURI__?: TauriLike }).__TAURI__ ?? null;
}

export async function readDesktopConfig(tauri: TauriLike | null = getTauri()): Promise<DesktopConfig> {
  const invoke = tauri?.core?.invoke;
  if (!invoke) throw new Error("仅在 Tauri 桌面壳中可用");
  return parseDesktopConfig(await invoke("read_desktop_config"));
}

export async function writeDesktopConfig(apiBaseUrl: string, tauri: TauriLike | null = getTauri()): Promise<DesktopConfig> {
  const invoke = tauri?.core?.invoke;
  if (!invoke) throw new Error("仅在 Tauri 桌面壳中可用");
  const normalized = normalizeApiBaseUrl(apiBaseUrl);
  return parseDesktopConfig(await invoke("write_desktop_config", { config: { api_base_url: normalized } }));
}

export async function openDesktopPath(command: DesktopCommand, tauri: TauriLike | null = getTauri()): Promise<void> {
  const invoke = tauri?.core?.invoke;
  if (!invoke) throw new Error("仅在 Tauri 桌面壳中可用");
  await invoke(command);
}

function parseDesktopConfig(value: unknown): DesktopConfig {
  if (!value || typeof value !== "object") return { apiBaseUrl: "" };
  const record = value as Record<string, unknown>;
  return { apiBaseUrl: normalizeApiBaseUrl(record.api_base_url) };
}
