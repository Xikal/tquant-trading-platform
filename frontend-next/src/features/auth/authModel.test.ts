import { describe, expect, it } from "vitest";
import { ApiError, ApiTransportError } from "../../shared/api/errors";
import { shouldClearStoredAuthAfterRestore } from "./authModel";

describe("auth restore persistence guard", () => {
  it("clears stored auth only when refresh is confirmed invalid", () => {
    expect(shouldClearStoredAuthAfterRestore(new ApiError(401, { detail: "expired" }), "invalid", true)).toBe(true);
    expect(shouldClearStoredAuthAfterRestore(new ApiError(401, { detail: "missing" }), "unavailable", false)).toBe(true);
  });

  it("keeps stored auth for transient restore failures so later refresh can recover", () => {
    expect(shouldClearStoredAuthAfterRestore(new ApiTransportError("aborted", "请求已取消"), "failed", true)).toBe(false);
    expect(shouldClearStoredAuthAfterRestore(new ApiTransportError("timeout", "请求超时"), "failed", true)).toBe(false);
    expect(shouldClearStoredAuthAfterRestore(new ApiError(503, { detail: "busy" }), "failed", true)).toBe(false);
  });
});
