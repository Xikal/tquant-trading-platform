import type { CSSProperties } from "react";
import { Input } from "antd";
import { appApi } from "../../api/appClient";
import type { AuthMfaSetupResponse, AuthUser } from "../../types";
import { SettingCard } from "../workspace-shared/WorkspaceComponents";
import { useSettingsUiStore } from "../../stores/settingsUiStore";
import { useServerState } from "../../state/serverState";

type AuthSecurityCardProps = {
  currentUser: AuthUser;
  onUserUpdate: (user: AuthUser) => void;
};

const SECURITY_CARD_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 10,
};

const SECURITY_STEP_GUIDE_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
};

const SECURITY_STEP_STYLE: CSSProperties = {
  border: "1px solid rgba(148, 163, 184, 0.24)",
  borderRadius: 10,
  background: "#f8fafc",
  color: "#334155",
  padding: 8,
  fontSize: 12,
  fontWeight: 800,
};

const SECURITY_SECRET_BOX_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  background: "#f8fafc",
  border: "1px solid #dbe3ef",
  borderRadius: 12,
  padding: "10px 12px",
};

const SECURITY_SECRET_CODE_STYLE: CSSProperties = {
  color: "#0f172a",
  fontSize: 13,
  overflowWrap: "anywhere",
};

const SECURITY_SUCCESS_STYLE: CSSProperties = {
  color: "#15803d",
};

const SECURITY_ERROR_STYLE: CSSProperties = {
  color: "#b91c1c",
  fontSize: 12,
  margin: 0,
};

const SECURITY_CODE_FIELD_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  minWidth: 0,
};

const SECURITY_CODE_LABEL_STYLE: CSSProperties = {
  color: "#62708a",
  fontSize: 12,
  fontWeight: 700,
};

const MFA_SETUP_SERVER_KEY = ["settings", "mfa", "setup"] as const;

export function AuthSecurityCard({ currentUser, onUserUpdate }: AuthSecurityCardProps) {
  const [setup, setSetup] = useServerState<AuthMfaSetupResponse | null>(MFA_SETUP_SERVER_KEY, null);
  const mfa = useSettingsUiStore((state) => state.mfa);
  const setMfa = useSettingsUiStore((state) => state.setMfa);
  const { code, loading, message, error } = mfa;

  async function startSetup() {
    await run(async () => {
      const payload = await appApi.setupTotp();
      setSetup(payload);
      setMfa({ message: "请把密钥加入认证器，然后输入 6 位验证码启用。" });
    });
  }

  async function enable() {
    if (!code.trim()) {
      setMfa({ error: "请输入认证器里的 6 位验证码" });
      return;
    }
    await run(async () => {
      const payload = await appApi.enableTotp(code.trim());
      onUserUpdate(payload.user);
      setSetup(null);
      setMfa({ code: "", message: "二次验证已启用，下次登录需要输入动态验证码。" });
    });
  }

  async function disable() {
    if (!code.trim()) {
      setMfa({ error: "请输入认证器里的 6 位验证码" });
      return;
    }
    await run(async () => {
      const payload = await appApi.disableTotp(code.trim());
      onUserUpdate(payload.user);
      setSetup(null);
      setMfa({ code: "", message: "二次验证已关闭。" });
    });
  }

  async function run(action: () => Promise<void>) {
    try {
      setMfa({ loading: true, error: "" });
      await action();
    } catch (err) {
      setMfa({ error: err instanceof Error ? err.message : "账号安全设置失败" });
    } finally {
      setMfa({ loading: false });
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
      <div style={SECURITY_CARD_GRID_STYLE}>
        <div>
          <strong>{enabled ? "二次验证已启用 · 安全评分 95/100" : "二次验证未启用 · 安全评分 70/100"}</strong>
          <p className="hint">建议有模拟盘、参数配置或管理权限的账号启用。验证码只用于登录校验，不会参与交易决策。</p>
        </div>
        <div style={SECURITY_STEP_GUIDE_STYLE} aria-label="二次验证开启步骤">
          <span style={SECURITY_STEP_STYLE}>1 下载认证器</span>
          <span style={SECURITY_STEP_STYLE}>2 保存密钥或扫码</span>
          <span style={SECURITY_STEP_STYLE}>3 输入 6 位验证码</span>
          <span style={SECURITY_STEP_STYLE}>4 启用后再登录验证</span>
        </div>
        {setup ? (
          <div style={SECURITY_SECRET_BOX_STYLE}>
            <span>认证器密钥</span>
            <code style={SECURITY_SECRET_CODE_STYLE}>{setup.secret}</code>
            <small>账号：{setup.account_name}，发行方：{setup.issuer}</small>
          </div>
        ) : null}
        <label style={SECURITY_CODE_FIELD_STYLE}>
          <span style={SECURITY_CODE_LABEL_STYLE}>动态验证码</span>
          <Input
            value={code}
            inputMode="numeric"
            maxLength={6}
            placeholder={enabled ? "关闭时输入 6 位验证码" : "启用时输入 6 位验证码"}
            onChange={(event) => setMfa({ code: event.target.value.replace(/\D/g, "").slice(0, 6) })}
          />
        </label>
        {message ? <p className="hint" style={SECURITY_SUCCESS_STYLE}>{message}</p> : null}
        {error ? <p style={SECURITY_ERROR_STYLE}>{error}</p> : null}
      </div>
    </SettingCard>
  );
}
