import { Profiler, type ProfilerOnRenderCallback, type ReactNode } from "react";
import type { WorkerComputeTelemetrySample } from "../workers/protocol";

declare global {
  interface Window {
    __TQUANT_FRONTEND_PERF__?: {
      commits: Array<{
        actualDuration: number;
        baseDuration: number;
        commitTime: number;
        id: string;
        phase: string;
        startTime: number;
      }>;
      workerTasks?: WorkerComputeTelemetrySample[];
    };
  }
}

export function PerformanceProfilerProbe({ children }: { children: ReactNode }) {
  if (typeof window === "undefined" || !frontendProfilerEnabled()) {
    return <>{children}</>;
  }
  window.__TQUANT_FRONTEND_PERF__ ??= { commits: [], workerTasks: [] };
  return (
    <Profiler id="web-app" onRender={recordCommit}>
      {children}
    </Profiler>
  );
}

export function frontendProfilerEnabled(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return new URLSearchParams(window.location.search).get("perf_profile") === "1";
}

const recordCommit: ProfilerOnRenderCallback = (
  id,
  phase,
  actualDuration,
  baseDuration,
  startTime,
  commitTime,
) => {
  const target = window.__TQUANT_FRONTEND_PERF__;
  if (!target) {
    return;
  }
  target.commits.push({
    actualDuration: Number(actualDuration.toFixed(3)),
    baseDuration: Number(baseDuration.toFixed(3)),
    commitTime: Number(commitTime.toFixed(3)),
    id,
    phase,
    startTime: Number(startTime.toFixed(3)),
  });
};
