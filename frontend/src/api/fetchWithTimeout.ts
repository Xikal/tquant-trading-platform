const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;

function abortWithReason(controller: AbortController, reason: DOMException) {
  try {
    controller.abort(reason);
  } catch {
    controller.abort();
  }
}

export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  let timedOut = false;
  let externallyAborted = false;
  const timeout = globalThis.setTimeout(() => {
    timedOut = true;
    abortWithReason(controller, new DOMException(`请求超过 ${Math.round(timeoutMs / 1000)} 秒未响应`, "TimeoutError"));
  }, timeoutMs);
  const externalSignal = init.signal;
  const abortFromExternal = () => {
    externallyAborted = true;
    abortWithReason(controller, new DOMException("请求已取消，请重试", "AbortError"));
  };
  if (externalSignal?.aborted) {
    abortFromExternal();
  } else {
    externalSignal?.addEventListener("abort", abortFromExternal, { once: true });
  }
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (timedOut) {
      throw new Error(`请求超过 ${Math.round(timeoutMs / 1000)} 秒未响应，请稍后重试`);
    }
    if (externallyAborted) {
      throw new Error("请求已取消，请重试");
    }
    if (error instanceof Error && /signal is aborted/i.test(error.message)) {
      throw new Error("请求已取消或超时，请稍后重试");
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", abortFromExternal);
  }
}
