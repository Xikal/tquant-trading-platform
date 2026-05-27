import { Capacitor, CapacitorHttp } from "@capacitor/core"

type HttpStatusError = Error & { status?: number }

function normalizeHeaders(headers?: HeadersInit): Record<string, string> {
  if (!headers) {
    return {}
  }
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries())
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers)
  }
  return Object.fromEntries(
    Object.entries(headers).map(([key, value]) => [key, String(value)])
  )
}

function resolveBody(body: BodyInit | null | undefined, headers: Record<string, string>) {
  if (!body) {
    return undefined
  }

  const contentType = Object.entries(headers).find(([key]) => key.toLowerCase() === "content-type")?.[1] ?? ""
  if (typeof body === "string" && contentType.includes("application/json")) {
    try {
      return JSON.parse(body) as unknown
    } catch {
      return body
    }
  }

  if (typeof body === "string") {
    return body
  }

  throw new Error("Native HTTP bridge only supports JSON or string request bodies.")
}

function resolvePayload(data: unknown, headers?: Record<string, string>) {
  const contentType = Object.entries(headers ?? {}).find(([key]) => key.toLowerCase() === "content-type")?.[1] ?? ""
  if (typeof data === "string" && contentType.includes("application/json")) {
    try {
      return JSON.parse(data) as unknown
    } catch {
      return data
    }
  }
  return data
}

export function isNativeHttpRuntime(isNativeTarget: boolean) {
  return isNativeTarget && Capacitor.isNativePlatform()
}

export async function nativeRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = normalizeHeaders(init?.headers)
  const response = await CapacitorHttp.request({
    url,
    method: init?.method ?? "GET",
    headers,
    data: resolveBody(init?.body, headers)
  })

  if (response.status < 200 || response.status >= 300) {
    const payload = resolvePayload(response.data, response.headers)
    let message = `Request failed: ${response.status}`
    if (payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string") {
      message = payload.detail
    } else if (typeof payload === "string" && payload.trim()) {
      message = payload
    }
    const error = new Error(message) as HttpStatusError
    error.status = response.status
    throw error
  }

  return resolvePayload(response.data, response.headers) as T
}
