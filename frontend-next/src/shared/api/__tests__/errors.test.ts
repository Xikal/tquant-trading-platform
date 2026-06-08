import { describe, expect, it } from "vitest";
import { ApiError, ApiTransportError, errorMessage } from "../errors";

describe("frontend-next API error messages", () => {
  it("redacts sensitive values before rendering user-facing error text", () => {
    const message = errorMessage(
      new ApiError(500, {
        detail: "请求失败 Authorization: Bearer access-token-123 access_token=token-456 password=unsafe",
      }),
    );

    expect(message).toContain("[redacted]");
    expect(message).not.toContain("access-token-123");
    expect(message).not.toContain("token-456");
    expect(message).not.toContain("unsafe");
  });

  it("redacts transport and generic error messages", () => {
    const transport = errorMessage(new ApiTransportError("network", "cookie=session-123 请求失败"));
    const generic = errorMessage(new Error("refresh_token=refresh-456 请求失败"));

    expect(transport).toBe("cookie=[redacted] 请求失败");
    expect(generic).toBe("refresh_token=[redacted] 请求失败");
  });
});
