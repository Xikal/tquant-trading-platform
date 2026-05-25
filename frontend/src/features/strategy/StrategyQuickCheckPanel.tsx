import { Button, Card, Col, Flex, Row, Space, Tag, Typography } from "antd";
import { DateField, NumberField, SelectField, TextField } from "../../components/shared/FormFields";
import type { StrategyMeta } from "../../api/strategies";
import { useStrategyHub } from "./useStrategyHub";

const RANGE_PRESETS = [
  { label: "最近 1 个月", days: 31 },
  { label: "最近 3 个月", days: 92 },
  { label: "最近 6 个月", days: 183 },
  { label: "最近 1 年", days: 365 },
];

const STYLE_PRESETS = [
  { key: "steady", label: "稳健", hint: "优先首板回调、缩量回调" },
  { key: "balanced", label: "平衡", hint: "覆盖当前生产策略" },
  { key: "aggressive", label: "激进", hint: "加入辅助策略做压力测试" },
] as const;

const ACTIVE_BUTTON_STYLE = {
  borderColor: "#91caff",
  background: "#e6f4ff",
  color: "#0958d9",
};

export function QuickBacktestForm({
  hub,
  onQuickSubmit,
}: {
  hub: ReturnType<typeof useStrategyHub>;
  onQuickSubmit: () => void;
}) {
  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Card size="small">
        <Flex align="center" justify="space-between" gap={12} wrap>
          <Space direction="vertical" size={2}>
            <Typography.Text strong>一键体检默认稳健策略</Typography.Text>
            <Typography.Text type="secondary">默认用 50 万模拟资金、真实费用和风控，普通用户不用改参数。</Typography.Text>
          </Space>
          <Button type="primary" onClick={onQuickSubmit} loading={hub.loading === "quick-submit"}>
            {hub.loading === "quick-submit" ? "提交中" : "开始体检"}
          </Button>
        </Flex>
      </Card>

      <Card size="small" title="快速体检设置" aria-label="快速体检设置">
        <Space direction="vertical" size={14} style={{ width: "100%" }}>
          <Space direction="vertical" size={2}>
            <Typography.Text strong>检查范围</Typography.Text>
            <Typography.Text type="secondary">时间越长越稳，但计算更慢。</Typography.Text>
          </Space>
          <Flex wrap gap={8}>
            {RANGE_PRESETS.map((preset) => {
              const active = isRangeActive(hub.form.start_date, preset.days);
              return (
                <Button
                  key={preset.label}
                  type={active ? "primary" : "default"}
                  onClick={() => hub.updateForm({ start_date: shiftDate(-preset.days), end_date: shiftDate(0) })}
                >
                  {preset.label}
                </Button>
              );
            })}
          </Flex>

          <Space direction="vertical" size={2}>
            <Typography.Text strong>策略风格</Typography.Text>
            <Typography.Text type="secondary">不懂策略时选“稳健”。</Typography.Text>
          </Space>
          <Row gutter={[8, 8]}>
            {STYLE_PRESETS.map((preset) => {
              const active = isStyleActive(hub.form.strategies, hub.strategies, preset.key);
              return (
                <Col key={preset.key} xs={24} sm={8}>
                  <Button
                    block
                    type="default"
                    onClick={() => hub.updateForm({ strategies: strategyKeysForStyle(hub.strategies, preset.key) })}
                    style={{ height: "auto", padding: "10px 12px", whiteSpace: "normal", textAlign: "left", ...(active ? ACTIVE_BUTTON_STYLE : undefined) }}
                  >
                    <Space direction="vertical" size={0} style={{ width: "100%" }}>
                      <Typography.Text strong>{preset.label}</Typography.Text>
                      <Typography.Text type="secondary">{preset.hint}</Typography.Text>
                    </Space>
                  </Button>
                </Col>
              );
            })}
          </Row>

          <StrategyPicker
            strategies={hub.strategies}
            selected={hub.form.strategies}
            onToggle={hub.toggleStrategy}
            onSelectSteady={() => hub.updateForm({ strategies: strategyKeysForStyle(hub.strategies, "steady") })}
            onSelectAll={() => hub.updateForm({ strategies: strategyKeysForStyle(hub.strategies, "aggressive") })}
          />

          <Row gutter={[12, 12]} aria-label="常用设置">
            <Col xs={24} md={12}>
              <NumberField
                label="单票仓位上限"
                suffix="%"
                value={hub.form.max_position_pct}
                onChange={(event) => hub.updateForm({ max_position_pct: event.target.value })}
              />
            </Col>
            <Col xs={24} md={12}>
              <TextField
                label="基准指数"
                value={hub.form.benchmark}
                onChange={(event) => hub.updateForm({ benchmark: event.target.value })}
              />
            </Col>
          </Row>

          <Flex
            justify="space-between"
            align="center"
            gap={12}
            style={{ border: "1px dashed #d9e2ec", borderRadius: 12, padding: "10px 12px", background: "#f8fafc" }}
          >
            <Typography.Text strong>预计耗时</Typography.Text>
            <Typography.Text type="secondary">{runtimeEstimate(hub.form.strategies.length, Number(hub.form.max_positions) || 0)}</Typography.Text>
          </Flex>
        </Space>
      </Card>

      <details style={{ border: "1px solid #dde6f0", borderRadius: 12, background: "#f8fafc", padding: 12 }}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>专业调优（最大持仓数、资金、成交模型等）</summary>
        <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
          <Col xs={24} md={12} xl={8}>
            <TextField label="任务名称" value={hub.form.name} onChange={(event) => hub.updateForm({ name: event.target.value })} />
          </Col>
          <Col xs={24} md={12} xl={8}>
            <DateField label="开始日期" value={hub.form.start_date} onChange={(event) => hub.updateForm({ start_date: event.target.value })} />
          </Col>
          <Col xs={24} md={12} xl={8}>
            <DateField label="结束日期" value={hub.form.end_date} onChange={(event) => hub.updateForm({ end_date: event.target.value })} />
          </Col>
          <Col xs={24} md={12} xl={8}>
            <NumberField label="初始资金" value={hub.form.initial_capital} onChange={(event) => hub.updateForm({ initial_capital: event.target.value })} />
          </Col>
          <Col xs={24} md={12} xl={8}>
            <SelectField
              label="成交模型"
              value={hub.form.execution_model}
              onChange={(event) => hub.updateForm({ execution_model: event.target.value as typeof hub.form.execution_model })}
              options={[
                { value: "open_price", label: "开盘价成交" },
                { value: "vwap", label: "VWAP 近似" },
                { value: "next_open", label: "次日开盘" },
                { value: "close_price", label: "收盘价成交" },
              ]}
            />
          </Col>
          <Col xs={24} md={12} xl={8}>
            <NumberField label="最大持仓数" value={hub.form.max_positions} onChange={(event) => hub.updateForm({ max_positions: event.target.value })} />
          </Col>
        </Row>
      </details>
    </Space>
  );
}

function StrategyPicker({
  strategies,
  selected,
  onToggle,
  onSelectSteady,
  onSelectAll,
}: {
  strategies: StrategyMeta[];
  selected: string[];
  onToggle: (key: string) => void;
  onSelectSteady: () => void;
  onSelectAll: () => void;
}) {
  const groups = groupStrategies(strategies);
  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Flex justify="space-between" align="center" gap={12} wrap>
        <Space direction="vertical" size={0}>
          <Typography.Text strong>策略选择（按风险分组）</Typography.Text>
          <Typography.Text type="secondary">{selected.length} 个已选</Typography.Text>
        </Space>
        <Flex gap={8} wrap>
          <Button type="default" size="small" onClick={onSelectSteady}>
            一键选稳健型
          </Button>
          <Button type="default" size="small" onClick={onSelectAll}>
            全选生产策略
          </Button>
        </Flex>
      </Flex>

      <Row gutter={[12, 12]}>
        {groups.map((group) => (
          <Col key={group.key} xs={24} lg={8}>
            <Card size="small" title={group.title}>
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {group.items.map((strategy) => {
                  const active = selected.includes(strategy.key);
                  return (
                    <Button
                      key={strategy.key}
                      block
                      type="default"
                      onClick={() => onToggle(strategy.key)}
                      style={{ height: "auto", padding: "8px 10px", whiteSpace: "normal", textAlign: "left", ...(active ? ACTIVE_BUTTON_STYLE : undefined) }}
                    >
                      <Space direction="vertical" size={2} style={{ width: "100%" }}>
                        <Flex justify="space-between" align="start" gap={12}>
                          <Typography.Text strong>{strategy.display_name || strategy.name}</Typography.Text>
                          <Tag color={phaseTagColor(strategy)}>{phaseBadge(strategy)}</Tag>
                        </Flex>
                        <Typography.Text type="secondary">{strategy.display_category || strategy.category}</Typography.Text>
                        <Typography.Text type="secondary" style={{ fontSize: 12, lineHeight: 1.4 }}>
                          {strategy.description}
                        </Typography.Text>
                      </Space>
                    </Button>
                  );
                })}
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </Space>
  );
}

function strategyKeysForStyle(strategies: StrategyMeta[], style: typeof STYLE_PRESETS[number]["key"]): string[] {
  const enabled = strategies.filter((item) => item.enabled !== false && item.visibility === "full");
  if (style === "steady") {
    return pickExisting(enabled, ["first_board", "volume_shrink"]);
  }
  if (style === "aggressive") {
    return enabled.filter((item) => item.tier === "core" || item.tier === "auxiliary").map((item) => item.key);
  }
  return enabled.filter((item) => item.tier === "core").map((item) => item.key);
}

function pickExisting(strategies: StrategyMeta[], preferred: string[]): string[] {
  const keys = new Set(strategies.map((item) => item.key));
  const picked = preferred.filter((key) => keys.has(key));
  return picked.length ? picked : strategies.slice(0, 2).map((item) => item.key);
}

function shiftDate(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function isRangeActive(startDate: string, days: number): boolean {
  const target = shiftDate(-days);
  return startDate === target;
}

function isStyleActive(selected: string[], strategies: StrategyMeta[], style: typeof STYLE_PRESETS[number]["key"]): boolean {
  const expected = strategyKeysForStyle(strategies, style);
  if (selected.length !== expected.length) return false;
  return [...selected].sort().join(",") === [...expected].sort().join(",");
}

function groupStrategies(strategies: StrategyMeta[]) {
  const enabled = strategies.filter((item) => item.enabled !== false && item.visibility === "full");
  return [
    {
      key: "steady",
      title: "🟢 稳健型",
      items: enabled.filter((item) => ["first_board", "volume_shrink"].includes(item.key)),
    },
    {
      key: "balanced",
      title: "🟡 均衡型",
      items: enabled.filter((item) => item.tier === "core" && !["first_board", "volume_shrink"].includes(item.key)),
    },
    {
      key: "aggressive",
      title: "🔴 激进型",
      items: enabled.filter((item) => item.tier === "auxiliary"),
    },
  ].filter((group) => group.items.length);
}

function phaseBadge(strategy: StrategyMeta): string {
  if (strategy.tier === "core") return "P3 已验证";
  if (strategy.tier === "auxiliary") return "P2 小仓验证";
  return "P1 观察";
}

function phaseTagColor(strategy: StrategyMeta): string {
  if (strategy.tier === "core") return "green";
  if (strategy.tier === "auxiliary") return "gold";
  return "default";
}

function runtimeEstimate(strategyCount: number, maxPositions: number): string {
  if (strategyCount <= 2 && maxPositions <= 5) return "< 1 分钟（轻量回测）";
  if (strategyCount <= 5) return "约 1-3 分钟（完整回测）";
  return "约 3-10 分钟（策略较多）";
}
