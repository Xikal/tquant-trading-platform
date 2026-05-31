import type { CSSProperties } from "react";
import type { AuthDraft } from "../workspace-shared/workspaceTypes";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Flex,
  Form,
  Input,
  Space,
  Tag,
  Typography,
} from "antd";
import { AppForm } from "../../ui/forms/AppForm";
import { ritualFortuneText } from "../ritual-ui";

const LOGIN_MAIN_STYLE: CSSProperties = {
  alignItems: "center",
  background: "radial-gradient(circle at 50% 38%, #17213a 0%, #08111f 46%, #030712 100%)",
  display: "grid",
  justifyItems: "center",
  minHeight: "100vh",
  overflow: "hidden",
  padding: "clamp(16px, 4vw, 32px)",
  position: "relative",
};
const LOGIN_TAG_STYLE: CSSProperties = {
  margin: 0,
};
const LOGIN_CARD_STYLE: CSSProperties = {
  backdropFilter: "blur(22px)",
  background: "linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.88))",
  border: "1px solid rgba(214, 165, 92, 0.34)",
  boxShadow: "0 28px 80px rgba(0, 0, 0, 0.42), 0 0 0 1px rgba(255, 255, 255, 0.28) inset",
  maxWidth: 430,
  position: "relative",
  width: "min(430px, calc(100vw - 32px))",
  zIndex: 2,
};
const LOGIN_CARD_BODY_STYLE: CSSProperties = {
  padding: "clamp(18px, 3vw, 26px)",
};
const LOGIN_FORM_STACK_STYLE: CSSProperties = {
  width: "100%",
};
const LOGIN_FORM_HEADER_STYLE: CSSProperties = {
  gap: 4,
  textAlign: "center",
  width: "100%",
};
const LOGIN_FORM_TITLE_STYLE: CSSProperties = {
  color: "#07111f",
  fontSize: 15,
  fontWeight: 700,
  margin: 0,
};
const LOGIN_FORM_COPY_STYLE: CSSProperties = {
  fontSize: 12,
  margin: 0,
};
const LOGIN_FORM_ITEM_STYLE: CSSProperties = {
  marginBottom: 0,
};
const LOGIN_SECURITY_NOTE_STYLE: CSSProperties = {
  color: "#6b7280",
  display: "block",
  fontSize: 12,
  lineHeight: 1.5,
  textAlign: "center",
};

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
    <main style={LOGIN_MAIN_STYLE}>
      <FinancialLoginBackdrop />
      <Card
        className="login-core-card"
        variant="borderless"
        style={LOGIN_CARD_STYLE}
        styles={{ body: LOGIN_CARD_BODY_STYLE }}
      >
        <AppForm<AuthDraft>
          layout="vertical"
          initialValues={draft}
          onValuesChange={(_, values) => setDraft({ ...draft, ...values })}
          onFinish={onLogin}
          requiredMark={false}
        >
          <Space direction="vertical" size={12} style={LOGIN_FORM_STACK_STYLE}>
            <Space direction="vertical" size={1} style={LOGIN_FORM_HEADER_STYLE}>
              <Typography.Title level={3} style={LOGIN_FORM_TITLE_STYLE}>
                维斯量化交易平台
              </Typography.Title>
              <Typography.Paragraph type="secondary" style={LOGIN_FORM_COPY_STYLE}>
                {loginStepText}
              </Typography.Paragraph>
            </Space>
            <Flex gap={8} justify="center" wrap>
              <Tag color="green" style={LOGIN_TAG_STYLE}>行情在线</Tag>
              <Tag color="gold" style={LOGIN_TAG_STYLE}>安全接入</Tag>
              <Tag color="blue" style={LOGIN_TAG_STYLE}>实时监控</Tag>
              <Tag color="red" style={LOGIN_TAG_STYLE}>今日红运</Tag>
            </Flex>
            <Form.Item
              name="username"
              label="手机号 / 账号"
              rules={[{ required: true, message: "请输入手机号或账号" }]}
              style={LOGIN_FORM_ITEM_STYLE}
            >
              <Input
                autoComplete="username"
                placeholder="请输入手机号或账号"
                disabled={loading}
                size="middle"
              />
            </Form.Item>
            <Form.Item
              name="password"
              label="登录密码"
              rules={[{ required: true, message: "请输入登录密码" }]}
              style={LOGIN_FORM_ITEM_STYLE}
            >
              <Input.Password
                autoComplete="current-password"
                placeholder="请输入登录密码"
                disabled={loading}
                size="middle"
              />
            </Form.Item>
            <Flex align="center" justify="space-between" wrap gap={8}>
              <Form.Item name="remember" valuePropName="checked" noStyle>
                <Checkbox disabled={loading}>记住登录</Checkbox>
              </Form.Item>
              <Button type="text" disabled={loading} title="请联系管理员重置密码">
                忘记密码？联系管理员
              </Button>
            </Flex>
            {error ? (
              <Alert
                type="error"
                showIcon
                message="登录失败"
                description={`${error}。请先检查账号和密码；连续失败会触发临时保护。`}
              />
            ) : null}
            <Button htmlType="submit" type="primary" loading={loading} block>
              {loading ? "验证成功，正在加载您的数据..." : "登录进入工作台"}
            </Button>
            <Button type="default" onClick={onRegister} disabled={loading} block>
              开户注册
            </Button>
            <Typography.Text style={LOGIN_SECURITY_NOTE_STYLE}>
              管理令牌、本机加密和行情缓存同步校验，进入后可直接查看盘中信号。
            </Typography.Text>
          </Space>
        </AppForm>
      </Card>
    </main>
  );
}

function FinancialLoginBackdrop() {
  const candles = [36, 72, 48, 94, 58, 112, 46, 86, 64, 126, 52, 98, 68, 118];
  const quoteTicks = ["上证 3128.42", "深成 9784.31", "沪深300 +0.62%", "中证1000 -0.18%", "成交额 8321亿"];
  const heatBlocks = [72, 38, 58, 91, 46, 64, 83, 29, 52, 76, 44, 68];
  return (
    <div className="login-finance-scene" aria-hidden="true">
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
            key={height + index}
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
        <span>数据质量 fresh</span>
      </div>
      <div className="login-heat-strip">
        {heatBlocks.map((value, index) => (
          <span
            key={`${value}-${index}`}
            className={value >= 60 ? "is-hot" : "is-cool"}
            style={{ "--heat": `${value}%`, "--heat-delay": `${index * 90}ms` } as CSSProperties}
          />
        ))}
      </div>
      <div className="login-ritual-seal">红运</div>
      <div className="login-ritual-motto">今日红运：{ritualFortuneText("neutral")}，纪律先行。</div>
    </div>
  );
}
