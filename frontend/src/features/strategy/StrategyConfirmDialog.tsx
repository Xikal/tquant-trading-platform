import { Button, Modal, Space, Typography } from "antd";

export function StrategyConfirmDialog({
  loading,
  title,
  description,
  summaryItems = [],
  onCancel,
  onConfirm,
}: {
  loading: boolean;
  title: string;
  description: string;
  summaryItems?: Array<{ label: string; value: string }>;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Modal
      open
      centered
      title={title}
      onCancel={onCancel}
      onOk={onConfirm}
      confirmLoading={loading}
      okText="✓ 确认，开始回测"
      cancelText="取消"
      footer={(
        <Space>
          <Button type="default" onClick={onCancel} disabled={loading}>取消</Button>
          <Button type="primary" onClick={onConfirm} loading={loading}>✓ 确认，开始回测</Button>
        </Space>
      )}
    >
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <Typography.Paragraph style={{ marginBottom: 0 }}>{description}</Typography.Paragraph>
        {summaryItems.length ? (
          <dl aria-label="提交确认摘要" style={{ display: "grid", gap: 8, margin: 0, padding: 12, border: "1px solid #e5e7eb", borderRadius: 8 }}>
            {summaryItems.map((item) => (
              <div key={item.label} style={{ display: "grid", gap: 10, gridTemplateColumns: "78px minmax(0, 1fr)" }}>
                <dt style={{ color: "#64748b", fontSize: 12, fontWeight: 600 }}>{item.label}</dt>
                <dd style={{ margin: 0, fontWeight: 600, overflowWrap: "anywhere" }}>{item.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </Space>
    </Modal>
  );
}
