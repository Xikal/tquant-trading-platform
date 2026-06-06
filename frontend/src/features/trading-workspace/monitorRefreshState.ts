export interface MonitorRefreshRequest {
  includeRuntime: boolean;
}

export interface MonitorRefreshStartResult {
  status: "started" | "queued";
  includeRuntime: boolean;
}

export function createMonitorRefreshState() {
  let inFlight = false;
  let queued: MonitorRefreshRequest | null = null;

  return {
    start(request: MonitorRefreshRequest): MonitorRefreshStartResult {
      if (inFlight) {
        queued = { includeRuntime: Boolean(queued?.includeRuntime || request.includeRuntime) };
        return { status: "queued", includeRuntime: queued.includeRuntime };
      }
      inFlight = true;
      return { status: "started", includeRuntime: request.includeRuntime };
    },
    finish(): { next: MonitorRefreshRequest | null } {
      const next = queued;
      queued = null;
      inFlight = Boolean(next);
      return { next };
    },
    reset() {
      inFlight = false;
      queued = null;
    },
  };
}
