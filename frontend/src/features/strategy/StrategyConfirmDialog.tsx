import { Button, Modal } from "antd";

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
        <div className="strategy-dialog-actions">
          <Button type="default" onClick={onCancel} disabled={loading}>取消</Button>
          <Button type="primary" onClick={onConfirm} loading={loading}>✓ 确认，开始回测</Button>
        </div>
      )}
    >
      <section className="strategy-dialog">
        <p>{description}</p>
        {summaryItems.length ? (
          <dl className="strategy-dialog-summary" aria-label="提交确认摘要">
            {summaryItems.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </section>
    </Modal>
  );
}
