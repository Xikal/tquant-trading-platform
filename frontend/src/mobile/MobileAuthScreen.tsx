import { Button, Input } from "antd-mobile"
import { useMobileUiStore } from "../stores/mobileUiStore"

interface MobileAuthScreenProps {
  loading: boolean
  error: string
  onSubmit: (payload: { username: string; password: string; register: boolean }) => Promise<void>
}

export function MobileAuthScreen({ loading, error, onSubmit }: MobileAuthScreenProps) {
  const authDraft = useMobileUiStore((state) => state.authDraft)
  const setAuthDraft = useMobileUiStore((state) => state.setAuthDraft)
  const { username, password, register, formError } = authDraft

  async function handleSubmit() {
    const nextUsername = username.trim()
    if (nextUsername.length < 3) {
      setAuthDraft({ formError: "账号至少 3 位" })
      return
    }
    if (password.length < 6) {
      setAuthDraft({ formError: "密码至少 6 位" })
      return
    }
    setAuthDraft({ formError: "" })
    await onSubmit({ username: nextUsername, password, register })
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
          <Input
            value={username}
            onChange={(value) => setAuthDraft({ username: value })}
            placeholder="请输入手机号或账号"
            autoCapitalize="none"
          />
        </label>

        <label className="mobile-auth-field">
          <span>登录密码</span>
          <Input
            value={password}
            onChange={(value) => setAuthDraft({ password: value })}
            placeholder="请输入登录密码"
            type="password"
          />
        </label>

        {formError || error ? <div className="mobile-app-error">{formError || error}</div> : null}

        <div className="mobile-auth-row">
          <span>☑ 记住登录</span>
          <Button fill="none" onClick={() => setAuthDraft({ register: !register })}>
            {register ? "返回登录" : "开户注册"}
          </Button>
        </div>

        <Button
          fill="solid"
          className="mobile-app-primary mobile-auth-submit"
          onClick={() => void handleSubmit()}
          loading={loading}
        >
          {loading ? "处理中" : register ? "注册并登录 →" : "登录进入工作台 →"}
        </Button>
        <div className="mobile-auth-safe-note">支持系统保存登录态；后续可接入 Face ID / 指纹快速打开。</div>
      </section>
    </div>
  )
}
