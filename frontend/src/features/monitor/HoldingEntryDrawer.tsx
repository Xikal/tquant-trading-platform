import { Button, Drawer } from "antd";
import { NumberField, SearchField, TextField } from "../../components/shared/FormFields";
import type { WatchDraft } from "../workspace-shared/workspaceTypes";
import { MonitorHoldingWizard } from "./MonitorHoldingWizard";

export function HoldingEntryDrawer({
  draft,
  editingSymbol,
  loading,
  open,
  setDraft,
  onAddWatchlist,
  onCancelEdit,
  onClose,
}: {
  draft: WatchDraft;
  editingSymbol: string;
  loading: string;
  open: boolean;
  setDraft: (draft: WatchDraft) => void;
  onAddWatchlist: () => void;
  onCancelEdit: () => void;
  onClose: () => void;
}) {
  const editing = Boolean(editingSymbol);
  return (
    <Drawer
      title={editing ? "编辑持仓约束" : "录入底仓约束"}
      open={open}
      onClose={onClose}
      width={420}
      extra={editing ? <Button htmlType="button" onClick={onCancelEdit}>取消编辑</Button> : null}
      destroyOnHidden
    >
      <p className="hint">{editing ? `正在编辑 ${editingSymbol}。` : "填写底仓、可卖和成本价，系统按 T+1 判断做T信号。"}</p>
      <MonitorHoldingWizard draft={draft} editing={editing} />
      <div className="monitor-holding-drawer__grid">
        <div className="monitor-holding-drawer__span">
          <SearchField
            label="证券代码"
            value={draft.symbol}
            placeholder="代码或名称"
            disabled={editing}
            onChange={(value) => setDraft({ ...draft, symbol: value })}
          />
        </div>
        <NumberField label="底仓数量" value={draft.base_position} onChange={(event) => setDraft({ ...draft, base_position: event.target.value })} />
        <NumberField label="可卖数量" value={draft.available_position} onChange={(event) => setDraft({ ...draft, available_position: event.target.value })} />
        <NumberField label="成本价" value={draft.cost_basis} onChange={(event) => setDraft({ ...draft, cost_basis: event.target.value })} />
        <TextField label="名称" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
        <div className="monitor-holding-drawer__span">
          <TextField label="备注" value={draft.memo} onChange={(event) => setDraft({ ...draft, memo: event.target.value })} />
        </div>
      </div>
      <Button type="primary" className="monitor-holding-drawer__action" onClick={onAddWatchlist} loading={loading === "watchlist"}>
        {loading === "watchlist" ? "保存中..." : editing ? "更新持仓" : draft.symbol.trim() ? "保存持仓" : "加入自选监控"}
      </Button>
    </Drawer>
  );
}
