import type { ReactNode } from "react";
import { Button, Flex, Form, Space, Typography } from "antd";
import type { ButtonProps, FormProps } from "antd";

export function AppForm<T extends object>({
  children,
  className = "",
  ...props
}: FormProps<T> & { children: ReactNode }) {
  return (
    <Form<T>
      layout="vertical"
      requiredMark={false}
      className={className || undefined}
      style={{ width: "100%" }}
      {...props}
    >
      {children}
    </Form>
  );
}

export function FormSection({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <Space direction="vertical" size={12} style={{ display: "flex" }}>
      <Flex align="baseline" justify="space-between" gap={12}>
        <Typography.Text strong>{title}</Typography.Text>
        {hint ? <Typography.Text type="secondary" style={{ fontSize: 12 }}>{hint}</Typography.Text> : null}
      </Flex>
      {children}
    </Space>
  );
}

export function SubmitBar({
  submitText = "保存",
  cancelText,
  loading,
  disabled,
  onCancel,
  children,
  submitProps,
}: {
  submitText?: string;
  cancelText?: string;
  loading?: boolean;
  disabled?: boolean;
  onCancel?: () => void;
  children?: ReactNode;
  submitProps?: ButtonProps;
}) {
  return (
    <Flex justify="flex-end" style={{ paddingTop: 8 }}>
      <Space wrap>
        {cancelText ? <Button onClick={onCancel} disabled={loading}>{cancelText}</Button> : null}
        <Button htmlType="submit" type="primary" loading={loading} disabled={disabled} {...submitProps}>
          {submitText}
        </Button>
        {children}
      </Space>
    </Flex>
  );
}
