export const REDACTED_TEXT = "[redacted]";

const SENSITIVE_KEY_PATTERN = /token|secret|password|authorization|cookie|credential|api[_-]?key/i;
const BEARER_TOKEN_PATTERN = /\bBearer\s+[A-Za-z0-9._~+/=-]{8,}/gi;
const SENSITIVE_ASSIGNMENT_PATTERN =
  /(["']?\b(?:access[_-]?token|refresh[_-]?token|admin[_-]?api[_-]?token|api[_-]?key|stream[_-]?token|secret|password|cookie|credential)\b["']?\s*[:=]\s*["']?)([^"'\s,&}]+)/gi;
const AUTHORIZATION_ASSIGNMENT_PATTERN =
  /(["']?\bauthorization\b["']?\s*[:=]\s*["']?)(Bearer\s+)?([^"'\s,&}]+)/gi;

export function isSensitiveFieldName(key: string): boolean {
  return SENSITIVE_KEY_PATTERN.test(key);
}

export function redactSensitiveText(value: unknown): string {
  const raw = value instanceof Error ? value.message : String(value ?? "");
  if (!raw) return raw;
  return raw
    .replace(BEARER_TOKEN_PATTERN, `Bearer ${REDACTED_TEXT}`)
    .replace(AUTHORIZATION_ASSIGNMENT_PATTERN, (_match, prefix: string, bearer: string | undefined) => `${prefix}${bearer ?? ""}${REDACTED_TEXT}`)
    .replace(SENSITIVE_ASSIGNMENT_PATTERN, (_match, prefix: string) => `${prefix}${REDACTED_TEXT}`);
}
