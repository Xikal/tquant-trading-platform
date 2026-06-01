import type { ReactNode } from "react";

interface ToolbarProps {
  left?: ReactNode;
  right?: ReactNode;
}

export function Toolbar({ left, right }: ToolbarProps) {
  return (
    <div className="tq-toolbar">
      <div className="tq-toolbar__side">{left}</div>
      <div className="tq-toolbar__side">{right}</div>
    </div>
  );
}
