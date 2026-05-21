import type { ReactNode } from "react";

type CommonProps = {
  children?: ReactNode;
  className?: string;
  disabled?: boolean;
  onClick?: () => void;
};

export function Button({ children, className, disabled, onClick }: CommonProps) {
  return (
    <button type="button" className={className} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

export function Input({
  value,
  onChange,
  placeholder,
  type,
  className,
}: {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  type?: string;
  className?: string;
}) {
  return (
    <input
      className={className}
      value={value ?? ""}
      placeholder={placeholder}
      type={type}
      onChange={(event) => onChange?.(event.currentTarget.value)}
    />
  );
}

export function NoticeBar({ children, content, className }: { children?: ReactNode; content?: ReactNode; className?: string }) {
  return <div className={className}>{children ?? content}</div>;
}

export function PullToRefresh({ children }: { children?: ReactNode; onRefresh?: () => Promise<unknown> | unknown }) {
  return <>{children}</>;
}

export function Popup({
  children,
  visible,
}: {
  children?: ReactNode;
  visible?: boolean;
  onMaskClick?: () => void;
  position?: string;
  bodyClassName?: string;
  destroyOnClose?: boolean;
}) {
  return visible ? <div>{children}</div> : null;
}

export function SafeArea({ children }: { children?: ReactNode }) {
  return <>{children}</>;
}

export function CapsuleTabs({ children }: { children?: ReactNode }) {
  return <div>{children}</div>;
}

CapsuleTabs.Tab = function CapsuleTab({ children }: { children?: ReactNode }) {
  return <div>{children}</div>;
};

export function TabBar({ children }: { children?: ReactNode }) {
  return <nav>{children}</nav>;
}

TabBar.Item = function TabBarItem({ children, title }: { children?: ReactNode; title?: ReactNode }) {
  return <div>{children ?? title}</div>;
};
