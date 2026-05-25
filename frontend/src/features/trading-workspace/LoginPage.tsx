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
  Statistic,
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
        background: "linear-gradient(145deg, #eef3f8 0%, #f8fafc 52%, #e9eff7 100%)",
        display: "flex",
        minHeight: "100vh",
        padding: 16,
      }}
    >
      <Row align="stretch" gutter={[16, 16]} style={{ margin: "0 auto", maxWidth: 1280, width: "100%" }}>
        <Col xs={24} lg={14}>
          <Card
            aria-label="盘中决策台概览"
            variant="borderless"
            style={{ background: "#0c1626", color: "#fff", height: "100%", minHeight: 560 }}
            styles={{
              body: {
                display: "flex",
                flexDirection: "column",
                gap: 24,
                height: "100%",
                justifyContent: "space-between",
                padding: 28,
              },
            }}
          >
            <Flex align="flex-start" gap={16} justify="space-between" wrap>
              <Space direction="vertical" size={4}>
                <Typography.Title level={1} style={{ color: "#fff", fontSize: 30, margin: 0 }}>
                  登录即进入盘中决策台
                </Typography.Title>
                <Typography.Text style={{ color: "#94a3b8", fontSize: 15 }}>
                  低吸候选、持仓风控与分析解释统一接入。
                </Typography.Text>
              </Space>
              <Tag color="gold">盘中在线</Tag>
            </Flex>

            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Row gutter={[12, 12]}>
                <Col xs={24} sm={12}>
                  <Card size="small" style={{ background: "#122239", borderColor: "#263951" }}>
                    <Statistic
                      title={<span style={{ color: "#94a3b8" }}>低吸机会</span>}
                      value="3 个确认"
                      valueStyle={{ color: "#f87171", fontSize: 24 }}
                    />
                  </Card>
                </Col>
                <Col xs={24} sm={12}>
                  <Card size="small" style={{ background: "#122239", borderColor: "#263951" }}>
                    <Statistic
                      title={<span style={{ color: "#94a3b8" }}>做 T 可执行</span>}
                      value="2 单通过"
                      valueStyle={{ color: "#f3bb5d", fontSize: 24 }}
                    />
                  </Card>
                </Col>
              </Row>
              <Card size="small" style={{ background: "#122239", borderColor: "#263951" }}>
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <Flex justify="space-between" wrap gap={8}>
                    <Typography.Text strong style={{ color: "#fff" }}>
                      交易保护
                    </Typography.Text>
                    <Tag color="green">风控校验已接入</Tag>
                  </Flex>
                  <Typography.Text style={{ color: "#cbd5e1" }}>
                    信号、仓位、止损与模拟交易均由平台统一校验，研究信号不会直接绕过风控下单。
                  </Typography.Text>
                  <Flex gap={8} wrap>
                    <Tag color="blue">行情同步</Tag>
                    <Tag color="gold">策略复盘</Tag>
                    <Tag color="red">风险提醒</Tag>
                  </Flex>
                </Space>
              </Card>
            </Space>

            <Typography.Text style={{ color: "#94a3b8", fontSize: 12 }}>
              界面示例仅用于说明平台能力，不构成收益承诺或交易建议。
            </Typography.Text>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Flex justify="center" vertical style={{ height: "100%" }}>
            <Card
              variant="borderless"
              style={{ border: "1px solid #dbe3ee", boxShadow: "0 20px 48px rgba(15, 23, 42, 0.08)" }}
              styles={{ body: { padding: 32 } }}
            >
              <AppForm<AuthDraft>
                layout="vertical"
                initialValues={draft}
                onValuesChange={(_, values) => setDraft({ ...draft, ...values })}
                onFinish={onLogin}
                requiredMark={false}
              >
                <Space direction="vertical" size={18} style={{ width: "100%" }}>
                  <Space direction="vertical" size={2} style={{ textAlign: "center", width: "100%" }}>
                    <Typography.Title level={2} style={{ margin: 0 }}>
                      登录维斯量化平台
                    </Typography.Title>
                    <Typography.Paragraph type="secondary" style={{ margin: 0 }}>
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
                      size="large"
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
                      size="large"
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
                  <Button htmlType="submit" size="large" type="primary" loading={loading} block>
                    {loading ? "验证成功，正在加载您的数据..." : "登录进入工作台"}
                  </Button>
                  <Button size="large" type="default" onClick={onRegister} disabled={loading} block>
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
