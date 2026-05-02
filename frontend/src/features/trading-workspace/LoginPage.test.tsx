import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  it("renders unified login copy and actions", () => {
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

    expect(html).toContain("登录维斯量化平台");
    expect(html).toContain("登录进入工作台");
    expect(html).toContain("开户注册");
  });
});
