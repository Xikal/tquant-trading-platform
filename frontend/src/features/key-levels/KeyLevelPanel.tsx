import { Alert, Collapse, Space, Tag } from "antd";
import type { KeyLevelResult } from "../../types";
import { InfoPill, MetricGrid, PanelTitle } from "../workspace-shared/WorkspaceComponents";
import { formatPct, formatPrice } from "../workspace-shared/workspaceFormatters";

interface KeyLevelPanelProps {
  title?: string;
  result?: KeyLevelResult | null;
  loading?: boolean;
  compact?: boolean;
}

export function KeyLevelPanel({
  title = "关键位观察",
  result,
  loading = false,
  compact = false,
}: KeyLevelPanelProps) {
  if (loading && !result) {
    return (
      <section className="key-level-panel">
        <PanelTitle title={title} />
        <Alert type="info" showIcon message="关键位加载中" />
      </section>
    );
  }
  if (!result) {
    return null;
  }
  if (shouldHideKeyLevelPanel(result)) {
    return null;
  }
  const supportText = zoneText(result.support_zone_low, result.support_zone_high, result.support_price);
  const resistanceText = zoneText(result.resistance_zone_low, result.resistance_zone_high, result.resistance_price);
  return (
    <section className="key-level-panel">
      <PanelTitle
        title={title}
        actions={(
          <Space size={4} wrap>
            <Tag>{scopeText(result.scope)}</Tag>
            <Tag color={qualityColor(result.data_quality)}>{qualityText(result.data_quality)}</Tag>
          </Space>
        )}
      />
      <Alert
        type={result.data_quality === "ok" ? "info" : "warning"}
        showIcon
        message={summaryText(result)}
        description={compact ? undefined : result.explanation}
      />
      <MetricGrid
        compact
        items={[
          { label: "最近支撑", value: supportText, tone: result.support_price ? "up" : "neutral" },
          { label: "距支撑", value: formatPct(result.support_distance_pct), tone: "neutral" },
          { label: "支撑强度", value: String(result.support_strength || "--"), tone: result.support_strength >= 70 ? "up" : "neutral" },
          { label: "最近压力", value: resistanceText, tone: result.resistance_price ? "warn" : "neutral" },
          { label: "距压力", value: formatPct(result.resistance_distance_pct), tone: "neutral" },
          { label: "压力强度", value: String(result.resistance_strength || "--"), tone: result.resistance_strength >= 70 ? "warn" : "neutral" },
          { label: "MA30", value: formatPrice(result.ma30), tone: result.trend_above_ma30 ? "up" : "neutral" },
          { label: "口径", value: `${result.adjust_mode} · ${result.engine_version}`, tone: "neutral" },
        ]}
      />
      <Collapse
        size="small"
        items={[
          {
            key: "details",
            label: "来源证据与失效条件",
            children: (
              <Space direction="vertical" size={8} style={{ display: "flex" }}>
                {result.warnings.map((item) => <Alert key={item} type="warning" showIcon message={item} />)}
                {result.key_level_candidates.slice(0, 6).map((item) => (
                  <div className="key-level-panel__candidate" key={`${item.direction}-${item.level_type}-${item.price}`}>
                    <Space size={4} wrap>
                      <Tag color={item.direction === "support" ? "green" : item.direction === "resistance" ? "orange" : "default"}>
                        {item.direction === "support" ? "支撑" : item.direction === "resistance" ? "压力" : "中性"}
                      </Tag>
                      <Tag>{sourceText(item.level_type)}</Tag>
                      <Tag>{formatPrice(item.price)}</Tag>
                      <Tag>{item.strength_score}</Tag>
                    </Space>
                    <div className="key-level-panel__evidence">{item.evidence.join("、") || "暂无证据说明"}</div>
                    <InfoPill compact label="失效条件" value={item.invalid_condition || "等待后续观察"} />
                  </div>
                ))}
              </Space>
            ),
          },
        ]}
      />
    </section>
  );
}

function shouldHideKeyLevelPanel(result: KeyLevelResult): boolean {
  return result.data_quality === "blocked" && result.warnings.some((item) => item.includes("功能开关关闭"));
}

function summaryText(result: KeyLevelResult): string {
  if (result.data_quality !== "ok" && result.data_quality !== "research_only") {
    return "数据不足，仅观察。";
  }
  if (result.support_price && result.resistance_price) {
    return `支撑 ${formatPrice(result.support_price)}，压力 ${formatPrice(result.resistance_price)}，仅用于观察。`;
  }
  if (result.support_price) return `最近支撑 ${formatPrice(result.support_price)}，仅用于观察。`;
  if (result.resistance_price) return `最近压力 ${formatPrice(result.resistance_price)}，仅用于观察。`;
  return "关键位不清晰，仅观察。";
}

function zoneText(low?: number | null, high?: number | null, price?: number | null): string {
  if (low && high) return `${formatPrice(low)}~${formatPrice(high)}`;
  return formatPrice(price);
}

function qualityText(value: KeyLevelResult["data_quality"]): string {
  const map = {
    ok: "可观察",
    insufficient: "数据不足",
    stale: "偏旧",
    blocked: "不可用",
    research_only: "研究观察",
  };
  return map[value] ?? value;
}

function qualityColor(value: KeyLevelResult["data_quality"]): string {
  if (value === "ok") return "green";
  if (value === "research_only") return "blue";
  if (value === "blocked") return "red";
  return "orange";
}

function scopeText(value: KeyLevelResult["scope"]): string {
  if (value === "market") return "大盘";
  if (value === "sector") return "板块";
  return "个股";
}

function sourceText(value: string): string {
  const map: Record<string, string> = {
    volume_profile: "成交密集区",
    platform_low: "平台低点",
    platform_high: "平台高点",
    swing_low: "前低",
    swing_high: "前高",
    anchored_vwap: "锚定均价",
    ma5: "MA5",
    ma10: "MA10",
    ma20: "MA20",
    ma30: "MA30",
    ma60: "MA60",
    intraday_vwap: "盘中 VWAP",
    open: "今开",
    prev_close: "昨收",
    round_number: "整数关口",
  };
  return map[value] ?? value;
}
