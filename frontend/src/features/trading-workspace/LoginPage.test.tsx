import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";

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
  });
});
