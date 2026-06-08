import { useNavigate } from "@tanstack/solid-router";
import { strategyCommandRegistry, strategyCommandSearchText, type StrategyCommand, type StrategyCommandTarget } from "../../shared/config/strategyCommands";
import { nextRoutes } from "../../shared/config/routes";
import { CommandPalette as CommandPaletteSurface, type CommandPaletteOption } from "../../shared/ui/CommandPalette";

type CommandItem =
  | (CommandPaletteOption & { type: "page"; path: string })
  | (CommandPaletteOption & { type: "strategy"; strategyKey: string; target: StrategyCommandTarget; searchText: string })
  | (CommandPaletteOption & { type: "symbol"; symbol: string });

export function CommandPalette(props: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();

  function execute(option: CommandPaletteOption) {
    const item = option as CommandItem;
    props.onClose();
    if (item.type === "symbol") {
      return navigate({ to: "/next/analysis", search: { symbol: item.symbol } });
    }
    if (item.type === "strategy") {
      if (item.target === "strategy-tracking") {
        return navigate({ to: "/next/strategy-tracking", search: { strategy_key: item.strategyKey } });
      }
      return navigate({ to: "/next/playbook", search: { strategy: item.strategyKey } });
    }
    return navigate({ to: item.path });
  }

  return (
    <CommandPaletteSurface
      open={props.open}
      getOptions={buildItems}
      onClose={props.onClose}
      onExecute={execute}
      placeholder="搜索页面、策略或输入 6 位股票代码"
      emptyText="没有匹配结果。输入股票代码可直接进入量化分析。"
    />
  );
}

function buildItems(query: string): CommandItem[] {
  const normalized = query.trim().toLowerCase();
  const symbolItems: CommandItem[] = /^\d{6}$/.test(normalized)
    ? [{ key: `symbol:${normalized}`, type: "symbol", label: `分析 ${normalized}`, hint: "跳转量化分析并填入代码", symbol: normalized }]
    : [];
  const pageItems: CommandItem[] = nextRoutes.map((route) => ({
    key: `page:${route.path}`,
    type: "page",
    label: route.label,
    hint: `${route.shortLabel} · ${route.legacyPath}`,
    path: route.path,
  }));
  const strategyItems: CommandItem[] = strategyCommandRegistry.map((strategy: StrategyCommand) => ({
    key: `strategy:${strategy.target}:${strategy.key}`,
    type: "strategy",
    label: strategy.label,
    hint: `打开${strategy.target === "playbook" ? "选股宝典" : "策略跟踪"} · ${strategy.scopeLabel}`,
    strategyKey: strategy.key,
    target: strategy.target,
    searchText: strategyCommandSearchText(strategy),
  }));
  const all = [...symbolItems, ...pageItems, ...strategyItems];
  if (!normalized) return all.slice(0, 12);
  return all
    .filter((item) => `${item.label} ${item.hint} ${item.type === "strategy" ? item.searchText : ""}`.toLowerCase().includes(normalized))
    .slice(0, 12);
}
