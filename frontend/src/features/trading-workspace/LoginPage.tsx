import type { AuthDraft } from "../workspace-shared/workspaceTypes";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Flex,
  Form,
  Input,
  Row,
  Space,
  Tag,
  Typography,
} from "antd";
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
    <main
      style={{
        alignItems: "center",
        background: "#f5f7fb",
        display: "flex",
        minHeight: "100vh",
        padding: 14,
      }}
    >
      <Row align="middle" gutter={[14, 14]} style={{ margin: "0 auto", maxWidth: 1040, width: "100%" }}>
        <Col xs={24} lg={10}>
          <section
            aria-label="盘中决策台概览"
            style={{
              background: "#101827",
              border: "1px solid rgba(148, 163, 184, 0.2)",
              borderRadius: 10,
              color: "#fff",
              display: "grid",
              gap: 12,
              padding: 18,
            }}
          >
            <Flex align="center" justify="space-between" gap={10} wrap>
              <Typography.Text style={{ color: "#94a3b8", fontSize: 12, fontWeight: 700 }}>
                盘中决策台
              </Typography.Text>
              <Tag color="gold" style={{ margin: 0 }}>在线</Tag>
            </Flex>
            <Typography.Title level={2} style={{ color: "#fff", fontSize: 24, lineHeight: 1.18, margin: 0 }}>
              登录即进入低吸、持仓与模拟盘工作流
            </Typography.Title>
            <Typography.Text style={{ color: "#cbd5e1", fontSize: 13 }}>
              信号、仓位、止损和模拟交易统一经过风控校验。
            </Typography.Text>
            <Flex gap={6} wrap>
              <Tag color="blue" style={{ margin: 0 }}>行情同步</Tag>
              <Tag color="green" style={{ margin: 0 }}>风控校验</Tag>
              <Tag color="red" style={{ margin: 0 }}>风险提醒</Tag>
            </Flex>
            <Typography.Text style={{ color: "#94a3b8", fontSize: 11 }}>
              不构成收益承诺或交易建议。
            </Typography.Text>
          </section>
        </Col>
        <Col xs={24} lg={14}>
          <Flex justify="center" vertical>
            <Card
              variant="borderless"
              style={{ border: "1px solid #dbe3ee", boxShadow: "0 12px 30px rgba(15, 23, 42, 0.07)" }}
              styles={{ body: { padding: 22 } }}
            >
              <AppForm<AuthDraft>
                layout="vertical"
                initialValues={draft}
                onValuesChange={(_, values) => setDraft({ ...draft, ...values })}
                onFinish={onLogin}
                requiredMark={false}
              >
                <Space orientation="vertical" size={12} style={{ width: "100%" }}>
                  <Space orientation="vertical" size={1} style={{ textAlign: "center", width: "100%" }}>
                    <Typography.Title level={3} style={{ fontSize: 22, margin: 0 }}>
                      登录维斯量化平台
                    </Typography.Title>
                    <Typography.Paragraph type="secondary" style={{ fontSize: 13, margin: 0 }}>
                      {loginStepText}
                    </Typography.Paragraph>
                  </Space>
                  <Flex gap={8} justify="center" wrap>
                    <Tag color="green">行情在线</Tag>
                    <Tag color="gold">安全接入</Tag>
                  </Flex>
                  <Form.Item
                    name="username"
                    label="手机号 / 账号"
                    rules={[{ required: true, message: "请输入手机号或账号" }]}
                    style={{ marginBottom: 0 }}
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
                    style={{ marginBottom: 0 }}
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
                  <Alert
                    type="info"
                    showIcon
                    message="登录保护"
                    description="管理令牌、本机加密和行情缓存同步校验，进入后可直接查看盘中信号。"
                  />
                </Space>
              </AppForm>
            </Card>
          </Flex>
        </Col>
      </Row>
    </main>
  );
}
