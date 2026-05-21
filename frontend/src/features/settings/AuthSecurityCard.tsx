import { useState } from "react";
import { appApi } from "../../api/appClient";
import type { AuthMfaSetupResponse, AuthUser } from "../../types";
import { SettingCard } from "../workspace-shared/WorkspaceComponents";

type AuthSecurityCardProps = {
  currentUser: AuthUser;
  onUserUpdate: (user: AuthUser) => void;
};

export function AuthSecurityCard({ currentUser, onUserUpdate }: AuthSecurityCardProps) {
  const [setup, setSetup] = useState<AuthMfaSetupResponse | null>(null);
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function startSetup() {
    await run(async () => {
      const payload = await appApi.setupTotp();
      setSetup(payload);
      setMessage("请把密钥加入认证器，然后输入 6 位验证码启用。");
    });
  }

  async function enable() {
    if (!code.trim()) {
      setError("请输入认证器里的 6 位验证码");
      return;
    }
    await run(async () => {
      const payload = await appApi.enableTotp(code.trim());
      onUserUpdate(payload.user);
      setSetup(null);
      setCode("");
      setMessage("二次验证已启用，下次登录需要输入动态验证码。");
    });
  }

  async function disable() {
    if (!code.trim()) {
      setError("请输入认证器里的 6 位验证码");
      return;
    }
    await run(async () => {
      const payload = await appApi.disableTotp(code.trim());
      onUserUpdate(payload.user);
      setSetup(null);
      setCode("");
      setMessage("二次验证已关闭。");
    });
  }

  async function run(action: () => Promise<void>) {
    try {
      setLoading(true);
      setError("");
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "账号安全设置失败");
    } finally {
      setLoading(false);
    }
  }

  const enabled = Boolean(currentUser.mfa_totp_enabled);
  return (
    <SettingCard
      title="账号安全"
      button={enabled ? "关闭二次验证" : setup ? "启用二次验证" : "生成二次验证密钥"}
      onSave={() => void (enabled ? disable() : setup ? enable() : startSetup())}
      loading={loading}
      disabled={loading}
    >
      <div className="security-card-grid">
        <div>
          <strong>{enabled ? "二次验证已启用 · 安全评分 95/100" : "二次验证未启用 · 安全评分 70/100"}</strong>
          <p className="hint">建议有模拟盘、参数配置或管理权限的账号启用。验证码只用于登录校验，不会参与交易决策。</p>
        </div>
        <div className="security-step-guide" aria-label="二次验证开启步骤">
          <span>1 下载认证器</span>
          <span>2 保存密钥或扫码</span>
          <span>3 输入 6 位验证码</span>
          <span>4 启用后再登录验证</span>
        </div>
        {setup ? (
          <div className="security-secret-box">
            <span>认证器密钥</span>
            <code>{setup.secret}</code>
            <small>账号：{setup.account_name}，发行方：{setup.issuer}</small>
          </div>
        ) : null}
        <label className="tq-field">
          <span>动态验证码</span>
          <input
            value={code}
            inputMode="numeric"
            maxLength={6}
            placeholder={enabled ? "关闭时输入 6 位验证码" : "启用时输入 6 位验证码"}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
          />
        </label>
        {message ? <p className="hint success-text">{message}</p> : null}
        {error ? <p className="field-error">{error}</p> : null}
      </div>
    </SettingCard>
  );
}
