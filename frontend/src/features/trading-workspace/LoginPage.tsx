import type { AuthDraft } from "../workspace-shared/workspaceTypes";
import { Alert, Button, Card, Checkbox, Form, Input, Space, Tag, Typography } from "antd";
import { AppForm } from "../../ui/forms/AppForm";

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
  const loginStepText = loading
    ? "验证成功后会自动加载您的持仓、榜单和模拟盘数据。"
    : "输入账号和密码即可进入工作台，系统会自动恢复您的持仓、榜单和模拟盘数据。";
  return (
    <main className="login-shell">
      <section className="login-visual" aria-label="盘中决策台概览">
        <div className="login-visual-head">
          <div>
            <h1>登录即进入盘中决策台</h1>
            <p>微信号、低吸候选、风控门槛与 AI 解释统一接入。</p>
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

        <Card className="login-card" variant="borderless">
          <AppForm<AuthDraft>
            layout="vertical"
            initialValues={draft}
            onValuesChange={(_, values) => setDraft({ ...draft, ...values })}
            onFinish={onLogin}
            requiredMark={false}
          >
            <div className="login-title">
              <Typography.Title level={2}>登录维斯量化平台</Typography.Title>
              <Typography.Paragraph>{loginStepText}</Typography.Paragraph>
            </div>
            <Space wrap className="login-status-row">
              <Tag color="red"><i className="red-dot" /> 行情在线</Tag>
              <Tag color="gold">安全接入</Tag>
            </Space>

            <Form.Item name="username" label="手机号 / 账号" rules={[{ required: true, message: "请输入手机号或账号" }]}>
              <Input
                autoComplete="username"
                placeholder="请输入手机号或账号"
                disabled={loading}
                prefix="⌕"
              />
            </Form.Item>

            <Form.Item name="password" label="登录密码" rules={[{ required: true, message: "请输入登录密码" }]}>
              <Input.Password
                autoComplete="current-password"
                placeholder="请输入登录密码"
                disabled={loading}
              />
            </Form.Item>

            <div className="login-options">
              <Form.Item name="remember" valuePropName="checked" noStyle>
                <Checkbox disabled={loading}>记住登录</Checkbox>
              </Form.Item>
              <Button type="text" disabled={loading} title="请联系管理员重置密码">忘记密码？联系管理员</Button>
            </div>

            {error ? (
              <Alert
                type="error"
                showIcon
                message="登录失败"
                description={`${error}。请先检查账号和密码；连续失败会触发临时保护。`}
              />
            ) : null}

            <Button htmlType="submit" type="primary" className="login-submit" loading={loading} block>
              {loading ? "验证成功，正在加载您的数据..." : "登录进入工作台"} <span aria-hidden="true">→</span>
            </Button>
            <Button type="default" className="login-register" onClick={onRegister} disabled={loading} block>
              开户注册
            </Button>

            <Alert
              className="login-protection"
              type="info"
              showIcon
              message="登录保护"
              description="管理令牌、本机加密和行情缓存同步校验，进入后可直接查看盘中信号。"
            />
          </AppForm>
        </Card>
      </section>
    </main>
  );
}
