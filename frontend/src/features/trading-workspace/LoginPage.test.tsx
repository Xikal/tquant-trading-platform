import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { isIpAddressLoginOrigin, LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  it("renders the centered login scene and actions", () => {
    const html = renderToStaticMarkup(
      <LoginPage
        draft={{ username: "", password: "", remember: true }}
        error=""
        loading={false}
        setDraft={vi.fn()}
        onLogin={vi.fn()}
        onRegister={vi.fn()}
      />
    );

    expect(html).toContain("维斯量化交易平台");
    expect(html).toContain("登录进入工作台");
    expect(html).toContain("开户注册");
    expect(html).toContain("login-finance-scene");
    expect(html).toContain("MARKET PULSE");
    expect(html).toContain("login-ritual-seal");
    expect(html).toContain("今日红运");
    expect(html).not.toContain("动态验证码");
    expect(html).not.toContain("当前是 IP 入口");
  });

  it("detects IP login origins that cannot reliably persist Secure refresh cookies", () => {
    expect(isIpAddressLoginOrigin("43.143.243.97")).toBe(true);
    expect(isIpAddressLoginOrigin("weisilianghua.cloud")).toBe(false);
    expect(isIpAddressLoginOrigin("www.weisilianghua.cloud")).toBe(false);
  });
});
