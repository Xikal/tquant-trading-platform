import type { ReactNode } from "react";
import { Button, Form, Space } from "antd";
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
      className={`app-form${className ? ` ${className}` : ""}`}
      {...props}
    >
      {children}
    </Form>
  );
}

export function FormSection({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="app-form-section">
      <div className="app-form-section-head">
        <strong>{title}</strong>
        {hint ? <span>{hint}</span> : null}
      </div>
      {children}
    </section>
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
    <div className="app-form-submit-bar">
      <Space wrap>
        {cancelText ? <Button onClick={onCancel} disabled={loading}>{cancelText}</Button> : null}
        <Button htmlType="submit" type="primary" loading={loading} disabled={disabled} {...submitProps}>
          {submitText}
        </Button>
        {children}
      </Space>
    </div>
  );
}
