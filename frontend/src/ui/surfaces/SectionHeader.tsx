import type { ReactNode } from "react";

interface SectionHeaderProps {
  actions?: ReactNode;
  desc?: ReactNode;
  title: ReactNode;
}

export function SectionHeader({ actions, desc, title }: SectionHeaderProps) {
  return (
    <header className="tq-section-header">
      <div className="tq-section-header__text">
        <h2 className="tq-section-header__title">{title}</h2>
        {desc ? <div className="tq-section-header__desc">{desc}</div> : null}
      </div>
      {actions}
    </header>
  );
}
