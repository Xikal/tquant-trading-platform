import { redactSensitiveText } from "../security/redaction";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  retryAfterMs?: number;

  constructor(status: number, detail: unknown, message?: string, retryAfterMs?: number) {
    super(message || `API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.retryAfterMs = retryAfterMs;
  }
}

export type ApiTransportErrorKind = "offline" | "timeout" | "network" | "aborted";

export class ApiTransportError extends Error {
  kind: ApiTransportErrorKind;

  constructor(kind: ApiTransportErrorKind, message: string) {
    super(message);
    this.name = "ApiTransportError";
    this.kind = kind;
  }
}

export function errorMessage(error: unknown): string {
  let message: string;
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") {
      message = error.detail;
      return redactSensitiveText(message);
    }
    if (error.detail && typeof error.detail === "object" && "detail" in error.detail) {
      message = String((error.detail as { detail?: unknown }).detail ?? error.message);
      return redactSensitiveText(message);
    }
    message = error.message;
    return redactSensitiveText(message);
  }
  if (error instanceof ApiTransportError) message = error.message;
  else if (error instanceof Error) message = error.message;
  else message = String(error || "未知错误");
  return redactSensitiveText(message);
}
