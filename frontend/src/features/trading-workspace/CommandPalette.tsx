import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Input } from "antd";
import type { InputRef } from "antd";
import type { StrategyMeta } from "../../api/strategies";
import { PRODUCTION_PLAYBOOK_TABS } from "../workspace-shared/workspaceConstants";
import type { Page } from "../workspace-shared/workspaceTypes";

interface CommandPaletteProps {
  open: boolean;
  strategies: StrategyMeta[];
  onClose: () => void;
  onNavigate: (page: Page) => void;
  onAnalyzeSymbol: (symbol: string) => void;
  onOpenStrategy: (strategyKey: string) => void;
}

type CommandItem =
  | { type: "page"; label: string; hint: string; page: Page }
  | { type: "strategy"; label: string; hint: string; strategyKey: string }
  | { type: "symbol"; label: string; hint: string; symbol: string };

const PAGE_COMMANDS: CommandItem[] = [
  { type: "page", label: "实时监控", hint: "打开持仓和全策略榜单", page: "monitor" },
  { type: "page", label: "量化分析", hint: "打开单票做T分析", page: "analysis" },
  { type: "page", label: "选股宝典", hint: "打开低吸策略候选", page: "playbook" },
  { type: "page", label: "策略工作台", hint: "打开回测、复盘、优化和对比", page: "strategy" },
  { type: "page", label: "模拟盘", hint: "打开模拟交易账户", page: "paper" },
  { type: "page", label: "系统配置", hint: "打开运行配置与治理", page: "settings" },
];

export function CommandPalette({
  open,
  strategies,
  onClose,
  onNavigate,
  onAnalyzeSymbol,
  onOpenStrategy,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<InputRef | null>(null);
  const items = useMemo(() => buildItems(query, strategies), [query, strategies]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
    const timer = window.setTimeout(() => inputRef.current?.focus(), 20);
    return () => window.clearTimeout(timer);
  }, [open]);

  if (!open) {
    return null;
  }

  const execute = (item: CommandItem) => {
    if (item.type === "page") {
      onNavigate(item.page);
    } else if (item.type === "strategy") {
      onOpenStrategy(item.strategyKey);
    } else {
      onAnalyzeSymbol(item.symbol);
    }
    onClose();
  };

  return (
    <div className="command-palette-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="command-palette" role="dialog" aria-modal="true" aria-label="全局搜索" onMouseDown={(event) => event.stopPropagation()}>
        <Input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              onClose();
            }
            if (event.key === "Enter" && items[0]) {
              execute(items[0]);
            }
          }}
          placeholder="搜索页面、策略或输入 6 位股票代码"
        />
        <div className="command-palette-list">
          {items.map((item) => (
            <Button type="text" key={`${item.type}-${item.label}`} onClick={() => execute(item)}>
              <strong>{item.label}</strong>
              <span>{item.hint}</span>
            </Button>
          ))}
          {!items.length ? (
            <div className="command-palette-empty">没有匹配结果。输入股票代码可直接跳转量化分析。</div>
          ) : null}
        </div>
        <footer>
          <span>Enter 执行</span>
          <span>Esc 关闭</span>
          <span>Cmd/Ctrl+1~6 切换页面</span>
        </footer>
      </section>
    </div>
  );
}

function buildItems(query: string, strategies: StrategyMeta[]): CommandItem[] {
  const normalized = query.trim().toLowerCase();
  const strategyItems: CommandItem[] = (strategies.length ? strategies : fallbackStrategies()).map((strategy) => ({
    type: "strategy",
    label: strategy.display_name || strategy.name || strategy.key,
    hint: `打开选股宝典 · ${strategy.display_category || strategy.category || "策略"}`,
    strategyKey: strategy.key,
  }));
  const symbolItem = /^\d{6}$/.test(normalized)
    ? [{ type: "symbol" as const, label: `分析 ${normalized}`, hint: "跳转量化分析并填入代码", symbol: normalized }]
    : [];
  const allItems = [...symbolItem, ...PAGE_COMMANDS, ...strategyItems];
  if (!normalized) {
    return allItems.slice(0, 12);
  }
  return allItems
    .filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(normalized))
    .slice(0, 12);
}

function fallbackStrategies(): StrategyMeta[] {
  return PRODUCTION_PLAYBOOK_TABS.map((item, index) => ({
    ...fallbackStrategyCategory(item.tier),
    key: item.key,
    name: item.label,
    display_name: item.label,
    description: "",
    tier: item.tier,
    category_key: item.tier,
    risk_level: "medium",
    typical_holding_days: "1-3天",
    sort_order: index,
  }));
}

function fallbackStrategyCategory(tier: string) {
  const label = tier === "core" ? "生产策略" : "辅助策略";
  return { category: label, display_category: label };
}
