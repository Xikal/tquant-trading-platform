import type { AuthDraft } from "./workspaceTypes";

interface LoginPageProps {
  draft: AuthDraft;
  error: string;
  loading: boolean;
  setDraft: (draft: AuthDraft) => void;
  onLogin: () => void;
  onRegister: () => void;
}

export function LoginPage({
  draft,
  error,
  loading,
  setDraft,
  onLogin,
  onRegister,
}: LoginPageProps) {
  return (
    <main className="login-shell">
      <section className="login-visual" aria-label="盘中决策台概览">
        <div className="login-visual-head">
          <div>
            <h1>登录即进入盘中决策台</h1>
            <p>微信号、低吸候选、风控阈值与 AI 解释统一接入。</p>
          </div>
          <span className="login-live-dot">盘中在线</span>
        </div>

        <div className="login-kpi-card">
          <div>
            <span>今日策略浮盈</span>
            <strong>+¥128,600</strong>
            <small>已覆盖 6 个自选 · 3 个可执行机会</small>
          </div>
          <div>
            <span>策略命中率</span>
            <strong className="danger">78%</strong>
            <small>风险席位 2</small>
          </div>
          <em>演示数据，仅用于说明界面能力，不代表真实收益。</em>
        </div>

        <div className="login-chart-card">
          <div className="login-chart-label">资金流入扫描</div>
          <div className="login-grid-lines" aria-hidden="true" />
          <svg className="login-chart-line" viewBox="0 0 720 180" role="img" aria-label="资金曲线">
            <path d="M8 150 C96 140 108 98 182 105 S285 122 354 68 492 78 566 54 646 72 712 34" />
          </svg>
          <div className="login-bars" aria-hidden="true">
            <span className="green" />
            <span className="red" />
            <span className="green" />
            <span className="red tall" />
            <span className="red" />
            <span className="green" />
            <span className="red" />
            <span className="gold" />
          </div>
          <span className="login-point blue" />
          <span className="login-point gold main" />
          <span className="login-point red" />
          <span className="login-point pale" />
          <span className="login-arrow">↗</span>
        </div>

        <div className="login-signal-grid">
          <div>
            <span>低吸机会</span>
            <strong className="danger">3 个确认</strong>
          </div>
          <div>
            <span>做T可执行</span>
            <strong>2 单通过</strong>
          </div>
        </div>

        <div className="login-mini-row">
          <div className="login-mini-chart">
            <div className="login-mini-line" />
            <span className="tag red">红盘突破</span>
            <span className="tag yellow">低吸 +3.6%</span>
            <span className="tag green">风控通过</span>
          </div>
          <div className="login-radar">
            <div className="radar-circle one" />
            <div className="radar-circle two" />
            <div className="radar-line" />
            <span />
            <strong>机会捕捉中</strong>
          </div>
        </div>
      </section>

      <section className="login-panel-wrap">
        <div className="login-market-pill">
          <span />
          <strong>上证指数 3278.62&nbsp;&nbsp;+0.86%</strong>
          <strong>资金净流入 ¥42.8亿</strong>
        </div>

        <form
          className="login-card"
          onSubmit={(event) => {
            event.preventDefault();
            onLogin();
          }}
        >
          <div className="login-title">
            <h2>登录维斯量化平台</h2>
            <p>同步盘中监控、选股宝典与研究复盘</p>
          </div>
          <div className="login-status-row">
            <span><i className="red-dot" /> 行情在线</span>
            <span className="gold"><i /> 安全接入</span>
          </div>

          <label className="login-field">
            <span>手机号 / 账号</span>
            <div>
              <b aria-hidden="true">⌕</b>
              <input
                value={draft.username}
                autoComplete="username"
                placeholder="请输入手机号或账号"
                disabled={loading}
                onChange={(event) => setDraft({ ...draft, username: event.target.value })}
              />
            </div>
          </label>

          <label className="login-field">
            <span>登录密码</span>
            <div>
              <b aria-hidden="true">□</b>
              <input
                value={draft.password}
                type="password"
                autoComplete="current-password"
                placeholder="请输入登录密码"
                disabled={loading}
                onChange={(event) => setDraft({ ...draft, password: event.target.value })}
              />
            </div>
          </label>

          <div className="login-options">
            <label>
              <input
                type="checkbox"
                checked={draft.remember}
                disabled={loading}
                onChange={(event) => setDraft({ ...draft, remember: event.target.checked })}
              />
              <span>记住登录</span>
            </label>
            <button type="button" disabled={loading}>忘记密码？</button>
          </div>

          {error ? <div className="login-error">{error}</div> : null}

          <button type="submit" className="login-submit" disabled={loading}>
            {loading ? "正在登录..." : "登录进入工作台"} <span aria-hidden="true">→</span>
          </button>
          <button type="button" className="login-register" onClick={onRegister} disabled={loading}>
            开户注册
          </button>

          <div className="login-protection">
            <strong>登录保护</strong>
            <p>管理令牌、本机加密和行情缓存同步校验，进入后可直接查看盘中信号。</p>
          </div>
        </form>
      </section>
    </main>
  );
}
