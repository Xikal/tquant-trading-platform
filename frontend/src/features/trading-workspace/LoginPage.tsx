import type { CSSProperties } from "react";
import type { AuthDraft } from "../workspace-shared/workspaceTypes";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Space,
  Typography,
} from "antd";
import { AppForm } from "../../ui/forms/AppForm";
import { ritualFortuneText } from "../ritual-ui";

const LOGIN_FORM_STACK_STYLE: CSSProperties = {
  width: "100%",
};
const LOGIN_FORM_ITEM_STYLE: CSSProperties = {
  marginBottom: 0,
};
const CERTIFICATE_DOMAIN_LOGIN_URL = "https://weisilianghua.cloud/monitor";

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
    ? "验证成功后会自动加载您的持仓、榜单和策略数据。"
    : "输入账号和密码即可进入工作台，系统会自动恢复您的持仓、榜单和策略数据。";
  const showIpEntryPersistenceWarning = isIpAddressLoginOrigin();

  return (
    <main className="wise-login-shell login-scanlines">
      <WiseLoginTicker />
      <FinancialLoginBackdrop />
      <section className="wise-login-stage">
        <Card
          className="login-core-card wise-login-card"
          variant="borderless"
        >
          <span className="wise-card-corner wise-card-corner-nw">乾卦</span>
          <span className="wise-card-corner wise-card-corner-ne">兑卦</span>
          <span className="wise-card-corner wise-card-corner-sw">坤卦</span>
          <span className="wise-card-corner wise-card-corner-se">坎卦</span>
          <AppForm<AuthDraft>
            className="wise-login-form"
            layout="vertical"
            initialValues={draft}
            onValuesChange={(_, values) => setDraft({ ...draft, ...values })}
            onFinish={onLogin}
            requiredMark={false}
          >
            <Space orientation="vertical" size={18} style={LOGIN_FORM_STACK_STYLE}>
              <Space orientation="vertical" size={6} className="wise-login-brand">
                <div className="wise-taiji-logo" aria-hidden="true">
                  <span className="wise-taiji-ring wise-taiji-ring-outer" />
                  <span className="wise-taiji-ring wise-taiji-ring-inner" />
                  <svg className="wise-taiji-mark" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2A10 10 0 0 0 2 12a10 10 0 0 0 10 10 10 10 0 0 0 10-10A10 10 0 0 0 12 2Zm0 2a8 8 0 0 1 8 8 8 8 0 0 1-8 8V4Zm0 2.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Zm0 10a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z" />
                  </svg>
                </div>
                <Typography.Title level={3} className="wise-login-title">
                  WISE <span>QUANT</span>
                </Typography.Title>
                <Typography.Paragraph className="wise-login-subtitle">
                  维斯量化交易平台 · 风控优先 · 数据校验
                </Typography.Paragraph>
              </Space>
              <div className="wise-login-mode-strip" aria-label="登录通道状态">
                <span>账号登录</span>
                <span>安全接入</span>
                <span>实时监控</span>
              </div>
              <Typography.Paragraph className="wise-login-copy">
                {loginStepText}
              </Typography.Paragraph>
              {showIpEntryPersistenceWarning ? (
                <Alert
                  className="wise-login-alert"
                  type="warning"
                  showIcon
                  message="当前是 IP 入口"
                  description={`浏览器的安全会话依赖证书域名，IP 入口下记住登录可能无法长期保存。建议使用 ${CERTIFICATE_DOMAIN_LOGIN_URL}`}
                />
              ) : null}
              <Form.Item
                name="username"
                label="USER ID / 账号"
                rules={[{ required: true, message: "请输入手机号或账号" }]}
                style={LOGIN_FORM_ITEM_STYLE}
              >
                <Input
                  autoComplete="username"
                  placeholder="请输入手机号或账号"
                  disabled={loading}
                  size="large"
                />
              </Form.Item>
              <Form.Item
                name="password"
                label="TERMINAL PASSPHRASE / 登录密码"
                rules={[{ required: true, message: "请输入登录密码" }]}
                style={LOGIN_FORM_ITEM_STYLE}
              >
                <Input.Password
                  autoComplete="current-password"
                  placeholder="请输入登录密码"
                  disabled={loading}
                  size="large"
                />
              </Form.Item>
              <div className="wise-login-options">
                <Form.Item name="remember" valuePropName="checked" noStyle>
                  <Checkbox disabled={loading}>记住登录</Checkbox>
                </Form.Item>
                <Button type="text" disabled={loading} title="请联系管理员重置密码">
                  忘记密码？联系管理员
                </Button>
              </div>
              {error ? (
                <Alert
                  className="wise-login-alert"
                  type="error"
                  showIcon
                  message="登录失败"
                  description={`${error}。请先检查账号和密码；连续失败会触发临时保护。`}
                />
              ) : null}
              <div className="wise-login-actions">
                <Button
                  className="wise-login-primary-btn"
                  htmlType="submit"
                  type="primary"
                  loading={loading}
                  block
                  size="large"
                >
                  {loading ? "验证成功，正在加载您的数据..." : "登录进入工作台"}
                </Button>
                <Button
                  className="wise-login-secondary-btn"
                  type="default"
                  onClick={onRegister}
                  disabled={loading}
                  block
                >
                  开户注册
                </Button>
              </div>
              <Typography.Text className="wise-login-security-note">
                管理令牌、本机加密和行情缓存同步校验，进入后可直接查看盘中信号。登录页展示不构成交易建议。
              </Typography.Text>
            </Space>
          </AppForm>
        </Card>
      </section>
      <footer className="wise-login-footer" aria-hidden="true">
        <span>SESSION ENCRYPTION: BAGUA-AES-512</span>
        <span>极限风控提示 · 登录后请先确认数据状态</span>
      </footer>
    </main>
  );
}

export function isIpAddressLoginOrigin(hostname = typeof window === "undefined" ? "" : window.location.hostname): boolean {
  const host = hostname.trim();
  return /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host) || host.startsWith("[");
}

function WiseLoginTicker() {
  const tickerItems = [
    { name: "上证指数", value: "3128.42", change: "+0.62%" },
    { name: "科创50", value: "928.50", change: "+1.18%" },
    { name: "东方财富", value: "28.88", change: "+2.02%" },
    { name: "宁德时代", value: "188.88", change: "+0.96%" },
    { name: "招商银行", value: "38.88", change: "+0.48%" },
  ];

  return (
    <header className="wise-login-ticker" aria-hidden="true">
      <div className="wise-login-ticker-track">
        {[...tickerItems, ...tickerItems].map((item, index) => (
          <span key={`${item.name}-${index}`}>
            <strong>{item.name}</strong>
            <em>{item.value}</em>
            <b>▲ {item.change}</b>
          </span>
        ))}
      </div>
    </header>
  );
}

function FinancialLoginBackdrop() {
  const candles = [36, 72, 48, 94, 58, 112, 46, 86, 64, 126, 52, 98, 68, 118];
  const quoteTicks = ["上证 3128.42", "深成 9784.31", "沪深300 +0.62%", "中证1000 -0.18%", "成交额 8321亿"];
  const heatBlocks = [72, 38, 58, 91, 46, 64, 83, 29, 52, 76, 44, 68];

  return (
    <div className="login-finance-scene" aria-hidden="true">
      <div className="login-purple-glow-field" />
      <div className="login-red-glow-field" />
      <div className="login-grid-layer" />
      <svg className="login-market-lines" viewBox="0 0 1200 720" preserveAspectRatio="none">
        <path className="login-market-line login-market-line-red" d="M0 458 C120 420 174 492 252 438 S420 350 520 392 S724 520 842 416 S1034 286 1200 334" />
        <path className="login-market-line login-market-line-green" d="M0 274 C126 318 180 222 292 252 S470 344 596 278 S794 176 912 232 S1080 374 1200 304" />
        <path className="login-market-line login-market-line-gold" d="M0 370 C150 356 236 300 348 332 S520 444 662 388 S852 300 992 342 S1110 404 1200 384" />
      </svg>
      <div className="login-radar-ring login-radar-ring-one" />
      <div className="login-radar-ring login-radar-ring-two" />
      <div className="login-orbit-dial">
        {Array.from({ length: 28 }).map((_, index) => (
          <span key={index} style={{ "--tick": String(index) } as CSSProperties} />
        ))}
      </div>
      <div className="login-ticker-strip login-ticker-strip-top">
        {[...quoteTicks, ...quoteTicks].map((item, index) => (
          <span key={`top-${item}-${index}`}>{item}</span>
        ))}
      </div>
      <div className="login-ticker-strip login-ticker-strip-bottom">
        {[...quoteTicks].reverse().concat(quoteTicks).map((item, index) => (
          <span key={`bottom-${item}-${index}`}>{item}</span>
        ))}
      </div>
      <div className="login-candle-field">
        {candles.map((height, index) => (
          <span
            className={index % 3 === 0 ? "is-down" : "is-up"}
            key={`${height}-${index}`}
            style={{ "--bar-height": `${height}px`, "--bar-delay": `${index * 120}ms` } as CSSProperties}
          />
        ))}
      </div>
      <div className="login-flow-node login-flow-node-one" />
      <div className="login-flow-node login-flow-node-two" />
      <div className="login-flow-node login-flow-node-three" />
      <div className="login-signal-pulse login-signal-pulse-one" />
      <div className="login-signal-pulse login-signal-pulse-two" />
      <div className="login-signal-pulse login-signal-pulse-three" />
      <div className="login-depth-panel login-depth-panel-left">
        {["买一", "买二", "买三", "买四", "买五"].map((item, index) => (
          <span key={item} style={{ "--depth": `${82 - index * 11}%` } as CSSProperties}>{item}</span>
        ))}
      </div>
      <div className="login-depth-panel login-depth-panel-right">
        {["卖一", "卖二", "卖三", "卖四", "卖五"].map((item, index) => (
          <span key={item} style={{ "--depth": `${38 + index * 10}%` } as CSSProperties}>{item}</span>
        ))}
      </div>
      <div className="login-hud-panel login-hud-panel-left">
        <strong>MARKET PULSE</strong>
        <span>情绪温度 58</span>
        <span>龙头强度 72</span>
        <span>全市场宽度 56%</span>
      </div>
      <div className="login-hud-panel login-hud-panel-right">
        <strong>RISK RADAR</strong>
        <span>回撤阈值 -3.5%</span>
        <span>仓位上限 45%</span>
        <span>数据质量 正常</span>
      </div>
      <aside className="wise-login-left-hud">
        <strong>FENGSHUI TELEMETRY</strong>
        <span>气场状态 <b>九紫离火 / ACTIVE</b></span>
        <span>信号纪律 <b>风控优先</b></span>
        <span>网络延迟 <b>12 ms</b></span>
        <div className="wise-login-spectrum">
          {heatBlocks.slice(0, 8).map((value, index) => (
            <i key={`${value}-${index}`} style={{ "--spectrum-height": `${18 + (value % 52)}%` } as CSSProperties} />
          ))}
        </div>
      </aside>
      <aside className="wise-login-right-hud">
        <strong>赛博高频招财符</strong>
        <div className="wise-talisman">
          <span>☯</span>
          <i />
        </div>
        <span>数据能量 98.4%</span>
      </aside>
      <div className="login-heat-strip">
        {heatBlocks.map((value, index) => (
          <span
            key={`${value}-${index}`}
            className={value >= 60 ? "is-hot" : "is-cool"}
            style={{ "--heat": `${value}%`, "--heat-delay": `${index * 90}ms` } as CSSProperties}
          />
        ))}
      </div>
      <div className="login-ritual-seal">纪律</div>
      <div className="login-ritual-motto">今日红运：{ritualFortuneText("neutral")}，纪律先行。</div>
    </div>
  );
}
