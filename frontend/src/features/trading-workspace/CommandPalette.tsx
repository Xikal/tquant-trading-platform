import type { CSSProperties } from "react";
import { useEffect, useMemo, useRef } from "react";
import { Button, Input } from "antd";
import type { InputRef } from "antd";
import type { StrategyMeta } from "../../api/strategies";
import { PRODUCTION_PLAYBOOK_TABS } from "../workspace-shared/workspaceConstants";
import type { Page } from "../workspace-shared/workspaceTypes";
import { useWorkspaceStore } from "../../stores/workspaceStore";
import { pageResponsibilityHint } from "./pageResponsibilities";

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
  { type: "page", label: "实时行动", hint: pageResponsibilityHint("monitor", "打开持仓和生产优先榜"), page: "monitor" },
  { type: "page", label: "市场环境", hint: pageResponsibilityHint("monitor-market", "打开市场宽度、板块轮动和复盘"), page: "monitor-market" },
  { type: "page", label: "量化分析", hint: "打开单票做T分析", page: "analysis" },
  { type: "page", label: "选股宝典", hint: "打开低吸策略候选", page: "playbook" },
  { type: "page", label: "策略跟踪", hint: "打开策略跟踪页面", page: "strategy-tracking" },
  { type: "page", label: "模拟盘", hint: pageResponsibilityHint("paper", "打开模拟交易账户"), page: "paper" },
  { type: "page", label: "数据", hint: "打开数据页面", page: "data" },
  { type: "page", label: "系统配置", hint: "打开运行配置与治理", page: "settings" },
];

const BACKDROP_STYLE: CSSProperties = {
  alignItems: "flex-start",
  background: "rgba(15, 23, 42, 0.38)",
  display: "flex",
  inset: 0,
  justifyContent: "center",
  paddingTop: "min(12vh, 96px)",
  position: "fixed",
  zIndex: 1100,
};

const PALETTE_STYLE: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #dbe3ef",
  borderRadius: 10,
  boxShadow: "0 28px 72px rgba(15, 23, 42, 0.28)",
  color: "#0f172a",
  overflow: "hidden",
  width: "min(680px, calc(100vw - 32px))",
};

const PALETTE_INPUT_STYLE: CSSProperties = {
  border: 0,
  borderBottom: "1px solid #e2e8f0",
  color: "#0f172a",
  fontSize: 12,
  outline: "none",
  padding: "10px 12px",
  width: "100%",
};

const PALETTE_LIST_STYLE: CSSProperties = {
  display: "grid",
  maxHeight: 420,
  overflow: "auto",
  padding: 8,
};

const PALETTE_ITEM_STYLE: CSSProperties = {
  alignItems: "center",
  background: "transparent",
  border: 0,
  borderRadius: 8,
  color: "#0f172a",
  cursor: "pointer",
  display: "grid",
  gap: 4,
  justifyItems: "start",
  padding: "7px 8px",
  textAlign: "left",
};

const PALETTE_ITEM_HOVER_STYLE: CSSProperties = {
  background: "#f3f6fb",
};

const PALETTE_ITEM_META_STYLE: CSSProperties = {
  color: "#64748b",
};

const PALETTE_EMPTY_STYLE: CSSProperties = {
  color: "#64748b",
  padding: "10px 8px",
};

const PALETTE_FOOTER_STYLE: CSSProperties = {
  alignItems: "center",
  background: "#f8fafc",
  borderTop: "1px solid #e2e8f0",
  display: "flex",
  flexWrap: "wrap",
  fontSize: 12,
  gap: 12,
  padding: "10px 14px",
  color: "#64748b",
};

export function CommandPalette({
  open,
  strategies,
  onClose,
  onNavigate,
  onAnalyzeSymbol,
  onOpenStrategy,
}: CommandPaletteProps) {
  const query = useWorkspaceStore((state) => state.commandQuery);
  const setQuery = useWorkspaceStore((state) => state.setCommandQuery);
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
    <div style={BACKDROP_STYLE} role="presentation" onMouseDown={onClose}>
      <section style={PALETTE_STYLE} role="dialog" aria-modal="true" aria-label="全局搜索" onMouseDown={(event) => event.stopPropagation()}>
        <Input
          ref={inputRef}
          variant="borderless"
          style={PALETTE_INPUT_STYLE}
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
        <div style={PALETTE_LIST_STYLE}>
          {items.map((item) => (
            <Button
              type="text"
              key={`${item.type}-${item.label}`}
              onClick={() => execute(item)}
              style={PALETTE_ITEM_STYLE}
              onMouseEnter={(event) => Object.assign(event.currentTarget.style, PALETTE_ITEM_HOVER_STYLE)}
              onMouseLeave={(event) => Object.assign(event.currentTarget.style, PALETTE_ITEM_STYLE)}
            >
              <strong>{item.label}</strong>
              <span style={PALETTE_ITEM_META_STYLE}>{item.hint}</span>
            </Button>
          ))}
          {!items.length ? (
            <div style={PALETTE_EMPTY_STYLE}>没有匹配结果。输入股票代码可直接跳转量化分析。</div>
          ) : null}
        </div>
        <footer style={PALETTE_FOOTER_STYLE}>
          <span>Enter 执行</span>
          <span>Esc 关闭</span>
          <span>Cmd/Ctrl+1~8 切换页面</span>
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
