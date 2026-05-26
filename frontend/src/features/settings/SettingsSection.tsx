import type { CSSProperties, ReactNode } from "react";

const SECTION_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  alignItems: "start",
  gap: 8,
  minWidth: 0,
  border: "1px solid rgba(148, 163, 184, 0.22)",
  borderRadius: 8,
  background: "rgba(248, 250, 252, 0.76)",
  padding: 8,
};

const ADMIN_SECTION_STYLE: CSSProperties = {
  borderColor: "rgba(214, 165, 92, 0.34)",
  background: "#fff8e8",
};

const TITLE_STYLE: CSSProperties = {
  display: "flex",
  gridColumn: "1 / -1",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: 8,
};

const TITLE_TEXT_STYLE: CSSProperties = {
  color: "#0f172a",
  fontSize: 13,
};

const DESCRIPTION_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 12,
};

export function SettingsSection({
  title,
  description,
  admin = false,
  children,
}: {
  title: string;
  description: string;
  admin?: boolean;
  children: ReactNode;
}) {
  return (
    <section style={admin ? { ...SECTION_STYLE, ...ADMIN_SECTION_STYLE } : SECTION_STYLE}>
      <div style={TITLE_STYLE}>
        <strong style={TITLE_TEXT_STYLE}>{title}</strong>
        <span style={DESCRIPTION_STYLE}>{description}</span>
      </div>
      {children}
    </section>
  );
}
