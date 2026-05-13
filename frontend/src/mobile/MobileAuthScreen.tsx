import { useState } from "react"

interface MobileAuthScreenProps {
  loading: boolean
  error: string
  onSubmit: (payload: { username: string; password: string; mfa_code?: string; register: boolean }) => Promise<void>
}

export function MobileAuthScreen({ loading, error, onSubmit }: MobileAuthScreenProps) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [mfaCode, setMfaCode] = useState("")
  const [register, setRegister] = useState(false)
  const [formError, setFormError] = useState("")

  async function handleSubmit() {
    const nextUsername = username.trim()
    if (nextUsername.length < 3) {
      setFormError("账号至少 3 位")
      return
    }
    if (password.length < 6) {
      setFormError("密码至少 6 位")
      return
    }
    setFormError("")
    await onSubmit({ username: nextUsername, password, mfa_code: mfaCode.trim() || undefined, register })
  }

  return (
    <div className="mobile-app-shell mobile-auth-shell">
      <section className="mobile-auth-hero" aria-label="登录动效">
        <div className="mobile-auth-status">
          <span>9:41</span>
          <span>5G ▰▰▰ ◔</span>
        </div>
        <span className="mobile-auth-online">● 行情在线</span>
        <div className="mobile-auth-head">
          <small>WEIS QUANT</small>
          <h1>维斯量化 TQuant</h1>
          <p>盘中监控、选股宝典、模拟交易统一接入。</p>
        </div>
        <div className="mobile-auth-profit">
          <span>今日策略浮盈</span>
          <strong>+¥128,600</strong>
          <small>命中率 78% · 3 个可执行机会</small>
          <small>演示数据，不代表真实收益</small>
        </div>
        <div className="mobile-auth-bars" aria-hidden="true">
          <i /><i /><i /><i /><i /><i /><i />
        </div>
        <div className="mobile-auth-radar" aria-hidden="true" />
      </section>

      <section className="mobile-auth-card">
        <div className="mobile-auth-card-head">
          <h2>登录进入工作台</h2>
          <p>同步持仓监控、低吸候选与研究复盘</p>
        </div>

        <label className="mobile-auth-field">
          <span>手机号 / 账号</span>
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="请输入手机号或账号"
            autoCapitalize="none"
          />
        </label>

        <label className="mobile-auth-field">
          <span>登录密码</span>
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="请输入登录密码"
            type="password"
          />
        </label>

        <label className="mobile-auth-field">
          <span>动态验证码</span>
          <input
            value={mfaCode}
            onChange={(event) => setMfaCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="已开启 MFA 时输入 6 位数字"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
          />
          <small>没有开启可留空；验证码来自手机 Authenticator App。</small>
        </label>

        {formError || error ? <div className="mobile-app-error">{formError || error}</div> : null}

        <div className="mobile-auth-row">
          <span>☑ 记住登录</span>
          <button type="button" onClick={() => setRegister((value) => !value)}>
            {register ? "返回登录" : "开户注册"}
          </button>
        </div>

        <button
          type="button"
          className="mobile-app-primary mobile-auth-submit"
          onClick={() => void handleSubmit()}
          disabled={loading}
        >
          {loading ? "处理中" : register ? "注册并登录 →" : "登录进入工作台 →"}
        </button>
        <div className="mobile-auth-safe-note">支持系统保存登录态；后续可接入 Face ID / 指纹快速打开。</div>
      </section>
    </div>
  )
}
