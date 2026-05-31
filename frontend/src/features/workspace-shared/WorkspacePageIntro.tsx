import type { CSSProperties, ReactNode } from "react";
import { Collapse, Typography } from "antd";
import { ContextRow, InfoPill } from "./WorkspaceComponents";
import type { Tone } from "./workspaceTypes";

const INTRO_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  minWidth: 0,
};

const INTRO_HEAD_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  justifyContent: "space-between",
  gap: 8,
  alignItems: "flex-start",
};

const INTRO_TEXT_STYLE: CSSProperties = {
  display: "grid",
  gap: 2,
  minWidth: 0,
  flex: "1 1 440px",
};

const INTRO_TITLE_BASE_STYLE: CSSProperties = {
  margin: 0,
  lineHeight: 1.15,
  letterSpacing: 0,
  fontSize: 13,
  fontWeight: 700,
};

const INTRO_SUMMARY_BASE_STYLE: CSSProperties = {
  margin: 0,
  fontSize: 12,
  lineHeight: 1.42,
};

const INTRO_DETAIL_BASE_STYLE: CSSProperties = {
  fontSize: 12,
  lineHeight: 1.45,
};

const INTRO_NOTE_BASE_STYLE: CSSProperties = {
  fontSize: 12,
  lineHeight: 1.45,
};

const INTRO_ACTIONS_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 6,
  alignItems: "center",
  justifyContent: "flex-end",
};

const LIGHT_STYLE: CSSProperties = {
  color: "#0f172a",
};

const DARK_STYLE: CSSProperties = {
  color: "#f8fafc",
};

const INTRO_COLLAPSE_STYLE: CSSProperties = {
  background: "transparent",
  fontSize: 12,
};

const INTRO_COLLAPSE_BODY_STYLE: CSSProperties = {
  padding: "4px 0 0",
};

const NOTE_LIGHT_STYLE: CSSProperties = {
  color: "#64748b",
};

const NOTE_DARK_STYLE: CSSProperties = {
  color: "#aeb8c7",
};

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
  const themeStyle = variant === "dark" ? DARK_STYLE : LIGHT_STYLE;
  const noteStyle = variant === "dark" ? NOTE_DARK_STYLE : NOTE_LIGHT_STYLE;
  return (
    <div style={{ ...INTRO_STYLE, ...themeStyle, ...style }}>
      <div style={INTRO_HEAD_STYLE}>
        <div style={INTRO_TEXT_STYLE}>
          <Typography.Text strong style={{ ...INTRO_TITLE_BASE_STYLE, ...themeStyle }}>
            {title}
          </Typography.Text>
          <Typography.Paragraph style={{ ...INTRO_SUMMARY_BASE_STYLE, ...themeStyle }}>
            {summary}
          </Typography.Paragraph>
          {detail ? (
            <Typography.Text style={{ ...INTRO_DETAIL_BASE_STYLE, ...noteStyle }}>
              {detail}
            </Typography.Text>
          ) : null}
        </div>
        {actions ? <div style={INTRO_ACTIONS_STYLE}>{actions}</div> : null}
      </div>
      {pills?.length ? (
        <ContextRow>
          {pills.map((item) => (
            <InfoPill key={`${item.label}-${item.value}`} compact label={item.label} value={item.value} tone={item.tone ?? "neutral"} />
          ))}
        </ContextRow>
      ) : null}
      {more ? (
        <Collapse
          ghost
          size="small"
          style={{ ...INTRO_COLLAPSE_STYLE, color: themeStyle.color }}
          items={[
            {
              key: "more",
              label: moreLabel,
              children: <Typography.Text style={{ ...INTRO_DETAIL_BASE_STYLE, ...noteStyle }}>{more}</Typography.Text>,
              styles: { body: INTRO_COLLAPSE_BODY_STYLE },
            },
          ]}
        />
      ) : null}
      {note ? (
        <Typography.Text style={{ ...INTRO_NOTE_BASE_STYLE, ...noteStyle }}>
          {note}
        </Typography.Text>
      ) : null}
    </div>
  );
}
