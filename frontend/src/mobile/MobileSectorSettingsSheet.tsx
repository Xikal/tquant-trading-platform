import { useEffect, useMemo, useState } from "react";
import { Button } from "antd-mobile";
import { Icon } from "./mobileSections";

export function MobileSectorSettingsSheet({
  open,
  availableSectors,
  excludedSectors,
  saving,
  onClose,
  onSave,
}: {
  open: boolean;
  availableSectors: string[];
  excludedSectors: string[];
  saving: boolean;
  onClose: () => void;
  onSave: (nextExcluded: string[]) => Promise<boolean>;
}) {
  const [selected, setSelected] = useState<string[]>(excludedSectors);

  useEffect(() => {
    if (open) {
      setSelected(excludedSectors);
    }
  }, [excludedSectors, open]);

  const summary = useMemo(() => {
    if (!selected.length) {
      return "当前没有排除任何行业，推荐会覆盖全部可交易行业。";
    }
    return `当前已排除 ${selected.length} 个行业，这些行业的股票不会再出现在实时监控、选股宝典和模拟盘推荐里。`;
  }, [selected]);

  if (!open) {
    return null;
  }

  function toggleSector(name: string) {
    setSelected((current) =>
      current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name],
    );
  }

  async function handleSave() {
    const ok = await onSave(selected);
    if (ok) {
      onClose();
    }
  }

  return (
    <div className="mobile-app-sheet-backdrop" role="presentation" onClick={onClose}>
      <section className="mobile-app-sheet mobile-sector-settings-sheet" onClick={(event) => event.stopPropagation()}>
        <div className="mobile-app-sheet-head">
          <div className="mobile-app-sheet-title">
            <h2>交易偏好</h2>
            <small>选择你不想参与的行业</small>
          </div>
          <Button fill="none" className="mobile-app-icon-button" onClick={onClose} aria-label="关闭">
            <Icon name="close" />
          </Button>
        </div>

        <div className="mobile-sector-settings-summary">
          <strong>行业排除</strong>
          <p>{summary}</p>
        </div>

        <div className="mobile-sector-tag-grid">
          {availableSectors.map((sector) => {
            const active = selected.includes(sector);
            return (
              <Button
                key={sector}
                fill={active ? "solid" : "outline"}
                color={active ? "primary" : "default"}
                className={`mobile-sector-tag ${active ? "active" : ""}`}
                onClick={() => toggleSector(sector)}
              >
                {sector}
              </Button>
            );
          })}
        </div>

        <div className="mobile-app-sheet-actions">
          <Button fill="outline" className="mobile-app-secondary" onClick={onClose}>
            取消
          </Button>
          <Button color="primary" className="mobile-app-primary" disabled={saving} onClick={() => void handleSave()}>
            {saving ? "保存中" : "保存偏好"}
          </Button>
        </div>
      </section>
    </div>
  );
}
