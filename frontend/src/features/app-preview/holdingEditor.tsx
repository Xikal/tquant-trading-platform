import { useEffect } from "react"
import { Button, Input, Popup } from "antd-mobile"
import type { WatchlistItem } from "../../types"
import { useMobileUiStore } from "../../stores/mobileUiStore"

export interface HoldingEditorSeed {
  symbol: string
  name: string
  base_position: number
  available_position: number
  cost_basis?: number | null
  memo?: string
}

function parseLots(raw: string) {
  const value = Number.parseInt(raw, 10)
  return Number.isFinite(value) ? Math.max(0, value) : 0
}

function parseCost(raw: string) {
  if (!raw.trim()) {
    return null
  }
  const value = Number.parseFloat(raw)
  return Number.isFinite(value) && value >= 0 ? value : null
}

function isLotAligned(value: number) {
  return value % 100 === 0
}

function stepLots(value: number, delta: number) {
  return Math.max(0, value + delta)
}

export function HoldingEditorSheet({
  open,
  seed,
  mode,
  saving,
  onClose,
  onSubmit
}: {
  open: boolean
  seed: HoldingEditorSeed
  mode: "create" | "buy" | "edit"
  saving: boolean
  onClose: () => void
  onSubmit: (payload: Omit<WatchlistItem, "created_at">) => Promise<void> | void
}) {
  const holdingForm = useMobileUiStore((state) => state.holdingForm)
  const setHoldingForm = useMobileUiStore((state) => state.setHoldingForm)
  const resetHoldingForm = useMobileUiStore((state) => state.resetHoldingForm)
  const { symbol, costBasis, basePosition, availablePosition, formError } = holdingForm

  useEffect(() => {
    if (!open) {
      return
    }
    resetHoldingForm(seed)
  }, [open, resetHoldingForm, seed])

  const numericBase = parseLots(basePosition)
  const numericAvailable = parseLots(availablePosition)

  async function handleSubmit() {
    const normalizedSymbol = symbol.trim().toUpperCase()
    const normalizedBase = parseLots(basePosition)
    const normalizedAvailable = parseLots(availablePosition)
    const normalizedCost = parseCost(costBasis)

    if (!normalizedSymbol) {
      setHoldingForm({ formError: "代码必填" })
      return
    }

    if (normalizedBase <= 0) {
      setHoldingForm({ formError: "持仓数大于 0" })
      return
    }

    if (!isLotAligned(normalizedBase) || !isLotAligned(normalizedAvailable)) {
      setHoldingForm({ formError: "股数填 100 的倍数" })
      return
    }

    if (normalizedAvailable > normalizedBase) {
      setHoldingForm({ formError: "可用数不能大于持仓" })
      return
    }

    setHoldingForm({ formError: "" })
    await onSubmit({
      symbol: normalizedSymbol,
      name: normalizedSymbol === seed.symbol.trim().toUpperCase() ? seed.name.trim() : "",
      base_position: normalizedBase,
      available_position: normalizedAvailable,
      cost_basis: normalizedCost,
      memo: seed.memo ?? ""
    })
  }

  const title = mode === "buy" ? "加入持仓" : mode === "create" ? "新增持仓" : "编辑持仓"

  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      position="bottom"
      bodyClassName="mobile-holding-editor-popup"
      destroyOnClose
    >
      <section className="mobile-app-sheet mobile-holding-editor">
        <div className="mobile-app-sheet-head">
          <div className="mobile-app-sheet-title">
            <h2>{title}</h2>
            <small>100 股递增</small>
          </div>
          <Button fill="none" className="mobile-app-icon-button" onClick={onClose} aria-label="关闭">
            ×
          </Button>
        </div>

        <div className="mobile-holding-form">
          <label className="mobile-holding-field">
            <span>代码</span>
            <Input
              value={symbol}
              onChange={(value) => setHoldingForm({ symbol: value.toUpperCase() })}
              placeholder="600000.SH"
              autoCapitalize="characters"
            />
          </label>
          <div className="mobile-holding-field-hint">
            {seed.name ? `名称 ${seed.name}` : "仅填代码，名称自动识别"}
          </div>

          <label className="mobile-holding-field">
            <span>成本价</span>
            <Input
              value={costBasis}
              onChange={(value) => setHoldingForm({ costBasis: value })}
              placeholder="0.000"
              inputMode="decimal"
            />
          </label>

          <div className="mobile-holding-field">
            <span>持仓数</span>
            <div className="mobile-stepper">
              <Button fill="none" className="mobile-step-button" onClick={() => setHoldingForm({ basePosition: String(stepLots(numericBase, -100)) })}>
                -100
              </Button>
              <Input
                value={basePosition}
                onChange={(value) => setHoldingForm({ basePosition: value })}
                inputMode="numeric"
              />
              <Button fill="none" className="mobile-step-button" onClick={() => setHoldingForm({ basePosition: String(stepLots(numericBase, 100)) })}>
                +100
              </Button>
            </div>
          </div>

          <div className="mobile-holding-field">
            <span>可用数</span>
            <div className="mobile-stepper">
              <Button
                fill="none"
                className="mobile-step-button"
                onClick={() => setHoldingForm({ availablePosition: String(stepLots(numericAvailable, -100)) })}
              >
                -100
              </Button>
              <Input
                value={availablePosition}
                onChange={(value) => setHoldingForm({ availablePosition: value })}
                inputMode="numeric"
              />
              <Button
                fill="none"
                className="mobile-step-button"
                onClick={() => setHoldingForm({ availablePosition: String(stepLots(numericAvailable, 100)) })}
              >
                +100
              </Button>
            </div>
          </div>
        </div>

        {formError ? <div className="mobile-app-error mobile-holding-error">{formError}</div> : null}

        <div className="mobile-holding-editor-actions">
          <div className="mobile-holding-editor-buttons">
            <Button fill="outline" className="mobile-app-secondary" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button color="primary" className="mobile-app-primary" onClick={() => void handleSubmit()} disabled={saving}>
              {saving ? "保存中" : "保存"}
            </Button>
          </div>
        </div>
      </section>
    </Popup>
  )
}
