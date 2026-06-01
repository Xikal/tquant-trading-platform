import type { CSSProperties, ReactNode } from "react";
import { Collapse, Typography } from "antd";
import { ContextRow, InfoPill } from "./WorkspaceComponents";
import type { Tone } from "./workspaceTypes";

export function WorkspacePageIntro({
  title,
  summary,
  detail,
  actions,
  pills,
  note,
  more,
  moreLabel = "更多",
  tone = "neutral",
  variant = "light",
  style,
}: {
  title: string;
  summary: ReactNode;
  detail?: ReactNode;
  actions?: ReactNode;
  pills?: Array<{ label: string; value: string; tone?: Tone }>;
  note?: ReactNode;
  more?: ReactNode;
  moreLabel?: string;
  tone?: Tone;
  variant?: "light" | "dark";
  style?: CSSProperties;
}) {
  return (
    <div
      className={`tq-workspace-intro tq-workspace-intro--tone-${tone} ${variant === "dark" ? "tq-workspace-intro--dark" : ""}`.trim()}
      style={style}
    >
      <div className="tq-workspace-intro__head">
        <div className="tq-workspace-intro__text">
          <Typography.Text strong className="tq-workspace-intro__title">
            {title}
          </Typography.Text>
          <Typography.Paragraph className="tq-workspace-intro__summary">
            {summary}
          </Typography.Paragraph>
          {detail ? (
            <Typography.Text className="tq-workspace-intro__detail">
              {detail}
            </Typography.Text>
          ) : null}
        </div>
        {actions ? <div className="tq-workspace-intro__actions">{actions}</div> : null}
      </div>
      {pills?.length ? (
        <ContextRow className="tq-workspace-intro__pills">
          {pills.map((item) => (
            <InfoPill key={`${item.label}-${item.value}`} compact label={item.label} value={item.value} tone={item.tone ?? "neutral"} />
          ))}
        </ContextRow>
      ) : null}
      {more ? (
        <Collapse
          ghost
          size="small"
          className="tq-workspace-intro__more"
          items={[
            {
              key: "more",
              label: moreLabel,
              children: <Typography.Text className="tq-workspace-intro__detail">{more}</Typography.Text>,
            },
          ]}
        />
      ) : null}
      {note ? (
        <Typography.Text className="tq-workspace-intro__note">
          {note}
        </Typography.Text>
      ) : null}
    </div>
  );
}
