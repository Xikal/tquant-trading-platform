import { DateField, NumberField, SelectField, TextField } from "../../components/shared/FormFields";
import type { StrategyMeta } from "../../api/strategies";
import { useStrategyHub } from "./useStrategyHub";

const RANGE_PRESETS = [
  { label: "近 3 个月", days: 92 },
  { label: "近 6 个月", days: 183 },
  { label: "近 12 个月", days: 365 },
];

const STYLE_PRESETS = [
  { key: "steady", label: "稳健", hint: "优先首板回调、缩量回调" },
  { key: "balanced", label: "平衡", hint: "覆盖当前生产策略" },
  { key: "aggressive", label: "激进", hint: "加入辅助策略做压力测试" },
] as const;

export function QuickBacktestForm({
  hub,
  onQuickSubmit,
}: {
  hub: ReturnType<typeof useStrategyHub>;
  onQuickSubmit: () => void;
}) {
  return (
    <div className="strategy-checkup">
      <section className="strategy-one-click">
        <div>
          <strong>一键体检默认稳健策略</strong>
          <span>默认用 50 万模拟资金、真实费用和风控，普通用户不用改参数。</span>
        </div>
        <button type="button" className="primary" onClick={onQuickSubmit} disabled={hub.loading === "quick-submit"}>
          {hub.loading === "quick-submit" ? "提交中" : "开始体检"}
        </button>
      </section>

      <section className="strategy-simple-setup" aria-label="快速体检设置">
        <div>
          <b>检查范围</b>
          <span>时间越长越稳，但计算更慢。</span>
        </div>
        <div className="strategy-chip-row">
          {RANGE_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className={isRangeActive(hub.form.start_date, preset.days) ? "active" : ""}
              onClick={() => hub.updateForm({ start_date: shiftDate(-preset.days), end_date: shiftDate(0) })}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <div>
          <b>策略风格</b>
          <span>不懂策略时选“稳健”。</span>
        </div>
        <div className="strategy-style-grid">
          {STYLE_PRESETS.map((preset) => (
            <button
              key={preset.key}
              type="button"
              className={isStyleActive(hub.form.strategies, hub.strategies, preset.key) ? "active" : ""}
              onClick={() => hub.updateForm({ strategies: strategyKeysForStyle(hub.strategies, preset.key) })}
            >
              <strong>{preset.label}</strong>
              <span>{preset.hint}</span>
            </button>
          ))}
        </div>
      </section>

      <details className="strategy-expert-settings">
        <summary>专家设置（不懂可以不展开）</summary>
        <div className="strategy-form">
          <TextField label="任务名称" value={hub.form.name} onChange={(event) => hub.updateForm({ name: event.target.value })} />
          <DateField label="开始日期" value={hub.form.start_date} onChange={(event) => hub.updateForm({ start_date: event.target.value })} />
          <DateField label="结束日期" value={hub.form.end_date} onChange={(event) => hub.updateForm({ end_date: event.target.value })} />
          <NumberField label="初始资金" value={hub.form.initial_capital} onChange={(event) => hub.updateForm({ initial_capital: event.target.value })} />
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
          <NumberField label="单票仓位上限" suffix="%" value={hub.form.max_position_pct} onChange={(event) => hub.updateForm({ max_position_pct: event.target.value })} />
          <NumberField label="最大持仓数" value={hub.form.max_positions} onChange={(event) => hub.updateForm({ max_positions: event.target.value })} />
          <TextField label="基准指数" value={hub.form.benchmark} onChange={(event) => hub.updateForm({ benchmark: event.target.value })} />
        </div>
        <StrategyPicker strategies={hub.strategies} selected={hub.form.strategies} onToggle={hub.toggleStrategy} />
      </details>
    </div>
  );
}

function StrategyPicker({
  strategies,
  selected,
  onToggle,
}: {
  strategies: StrategyMeta[];
  selected: string[];
  onToggle: (key: string) => void;
}) {
  return (
    <div className="strategy-picker">
      <div className="strategy-picker-head">
        <strong>具体策略</strong>
        <span>{selected.length} 个已选</span>
      </div>
      <div className="strategy-card-grid">
        {strategies.map((strategy) => (
          <button
            type="button"
            key={strategy.key}
            className={selected.includes(strategy.key) ? "selected" : ""}
            onClick={() => onToggle(strategy.key)}
          >
            <strong>{strategy.display_name || strategy.name}</strong>
            <span>{strategy.display_category || strategy.category}</span>
            <small>{strategy.description}</small>
          </button>
        ))}
      </div>
    </div>
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
  if (selected.length !== expected.length) {
    return false;
  }
  const selectedKeys = [...selected].sort().join(",");
  const expectedKeys = [...expected].sort().join(",");
  return selectedKeys === expectedKeys;
}
