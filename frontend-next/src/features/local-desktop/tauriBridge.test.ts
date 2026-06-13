import { describe, expect, it, vi } from "vitest";
import { openDesktopPath, readDesktopConfig, writeDesktopConfig } from "./tauriBridge";

describe("tauriBridge", () => {
  it("reads desktop config from Tauri when available", async () => {
    const invoke = vi.fn().mockResolvedValue({ api_base_url: "http://127.0.0.1:8000" });

    const config = await readDesktopConfig({ core: { invoke } });

    expect(config).toEqual({ apiBaseUrl: "http://127.0.0.1:8000" });
    expect(invoke).toHaveBeenCalledWith("read_desktop_config");
  });

  it("writes normalized desktop config through Tauri", async () => {
    const invoke = vi.fn().mockResolvedValue({ api_base_url: "http://localhost:9000" });

    const config = await writeDesktopConfig(" http://localhost:9000/ ", { core: { invoke } });

    expect(config).toEqual({ apiBaseUrl: "http://localhost:9000" });
    expect(invoke).toHaveBeenCalledWith("write_desktop_config", {
      config: { api_base_url: "http://localhost:9000" },
    });
  });

  it("returns unavailable errors outside Tauri", async () => {
    await expect(readDesktopConfig(null)).rejects.toThrow("仅在 Tauri 桌面壳中可用");
    await expect(openDesktopPath("open_log_dir", null)).rejects.toThrow("仅在 Tauri 桌面壳中可用");
  });
});
