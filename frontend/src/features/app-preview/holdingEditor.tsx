import { useEffect, useState } from "react"
import type { WatchlistItem } from "../../types"

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
  const [symbol, setSymbol] = useState("")
  const [costBasis, setCostBasis] = useState("")
  const [basePosition, setBasePosition] = useState("0")
  const [availablePosition, setAvailablePosition] = useState("0")
  const [formError, setFormError] = useState("")

  useEffect(() => {
    if (!open) {
      return
    }
    setSymbol(seed.symbol)
    setCostBasis(
      typeof seed.cost_basis === "number" && Number.isFinite(seed.cost_basis) ? String(seed.cost_basis) : ""
    )
    setBasePosition(String(seed.base_position))
    setAvailablePosition(String(seed.available_position))
    setFormError("")
  }, [open, seed])

  if (!open) {
    return null
  }

  const numericBase = parseLots(basePosition)
  const numericAvailable = parseLots(availablePosition)

  async function handleSubmit() {
    const normalizedSymbol = symbol.trim().toUpperCase()
    const normalizedBase = parseLots(basePosition)
    const normalizedAvailable = parseLots(availablePosition)
    const normalizedCost = parseCost(costBasis)

    if (!normalizedSymbol) {
      setFormError("代码必填")
      return
    }

    if (normalizedBase <= 0) {
      setFormError("持仓数大于 0")
      return
    }

    if (!isLotAligned(normalizedBase) || !isLotAligned(normalizedAvailable)) {
      setFormError("股数填 100 的倍数")
      return
    }

    if (normalizedAvailable > normalizedBase) {
      setFormError("可用数不能大于持仓")
      return
    }

    setFormError("")
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
    <div className="mobile-app-sheet-backdrop mobile-holding-editor-backdrop" role="presentation" onClick={onClose}>
      <section className="mobile-app-sheet mobile-holding-editor" onClick={(event) => event.stopPropagation()}>
        <div className="mobile-app-sheet-head">
          <div className="mobile-app-sheet-title">
            <h2>{title}</h2>
            <small>100 股递增</small>
          </div>
          <button type="button" className="mobile-app-icon-button" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>

        <div className="mobile-holding-form">
          <label className="mobile-holding-field">
            <span>代码</span>
            <input
              value={symbol}
              onChange={(event) => setSymbol(event.target.value.toUpperCase())}
              placeholder="600000.SH"
              autoCapitalize="characters"
            />
          </label>
          <div className="mobile-holding-field-hint">
            {seed.name ? `名称 ${seed.name}` : "仅填代码，名称自动识别"}
          </div>

          <label className="mobile-holding-field">
            <span>成本价</span>
            <input
              value={costBasis}
              onChange={(event) => setCostBasis(event.target.value)}
              placeholder="0.000"
              inputMode="decimal"
            />
          </label>

          <div className="mobile-holding-field">
            <span>持仓数</span>
            <div className="mobile-stepper">
              <button type="button" className="mobile-step-button" onClick={() => setBasePosition(String(stepLots(numericBase, -100)))}>
                -100
              </button>
              <input
                value={basePosition}
                onChange={(event) => setBasePosition(event.target.value)}
                inputMode="numeric"
              />
              <button type="button" className="mobile-step-button" onClick={() => setBasePosition(String(stepLots(numericBase, 100)))}>
                +100
              </button>
            </div>
          </div>

          <div className="mobile-holding-field">
            <span>可用数</span>
            <div className="mobile-stepper">
              <button
                type="button"
                className="mobile-step-button"
                onClick={() => setAvailablePosition(String(stepLots(numericAvailable, -100)))}
              >
                -100
              </button>
              <input
                value={availablePosition}
                onChange={(event) => setAvailablePosition(event.target.value)}
                inputMode="numeric"
              />
              <button
                type="button"
                className="mobile-step-button"
                onClick={() => setAvailablePosition(String(stepLots(numericAvailable, 100)))}
              >
                +100
              </button>
            </div>
          </div>
        </div>

        {formError ? <div className="mobile-app-error mobile-holding-error">{formError}</div> : null}

        <div className="mobile-holding-editor-actions">
          <div className="mobile-holding-editor-buttons">
            <button type="button" className="mobile-app-secondary" onClick={onClose} disabled={saving}>
              取消
            </button>
            <button type="button" className="mobile-app-primary" onClick={() => void handleSubmit()} disabled={saving}>
              {saving ? "保存中" : "保存"}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
