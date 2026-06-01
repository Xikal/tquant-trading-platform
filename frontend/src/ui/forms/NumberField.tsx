import { Form, InputNumber } from "antd";

export function NumberField({
  name,
  label,
  min,
  max,
  step,
}: {
  name: string;
  label: string;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <Form.Item name={name} label={label}>
      <InputNumber min={min} max={max} step={step} className="tq-number-field" />
    </Form.Item>
  );
}
