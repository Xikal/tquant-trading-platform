import { useEffect, useState } from "react"
import type {
  AppAndroidUpdateResponse,
  AuthUser,
  LowBuyPriorityBoardItem,
  LowBuyPriorityBoardResult,
  PaperOrderCreate
} from "../types"
import { formatPct, formatPrice } from "../features/trading-workspace/workspaceFormatters"
import { Icon } from "./mobileSections"

export function AccountMenu({
  user,
  open,
  onToggle,
  onLogout
}: {
  user: AuthUser
  open: boolean
  onToggle: () => void
  onLogout: () => void
}) {
  const displayName = user.display_name || user.username
  return (
    <div className="mobile-account-menu-wrap">
      <button
        type="button"
        className="mobile-app-icon-button mobile-account-button"
        onClick={onToggle}
        aria-expanded={open}
      >
        <span>{displayName}</span>
      </button>
      {open ? (
        <div className="mobile-account-menu">
          <strong>{displayName}</strong>
          <small>{user.username}</small>
          <button type="button" onClick={onLogout}>
            退出登录
          </button>
        </div>
      ) : null}
    </div>
  )
}

export function PriorityActionSheet({
  item,
  onClose,
  onOpenDetail,
  onMarkBought
}: {
  item: LowBuyPriorityBoardItem | null
  onClose: () => void
  onOpenDetail: (symbol: string) => void | Promise<void>
  onMarkBought: (item: LowBuyPriorityBoardItem) => void
}) {
  if (!item) {
    return null
  }
  const strategies = item.strategy_titles?.length ? item.strategy_titles.join(" / ") : item.strategy_title || "全策略"
  const mainline = item.industry_tier_text || item.industry_tier || "主线状态待确认"

  return (
    <div className="mobile-app-sheet-backdrop" role="presentation" onClick={onClose}>
      <section className="mobile-app-sheet mobile-priority-action-sheet" onClick={(event) => event.stopPropagation()}>
        <div className="mobile-app-sheet-head">
          <div className="mobile-app-sheet-title">
            <h2>{item.name} {item.symbol}</h2>
            <small>{item.buy_signal_text || "等待确认"}</small>
          </div>
          <button type="button" className="mobile-app-icon-button" onClick={onClose} aria-label="关闭">
            <Icon name="close" />
          </button>
        </div>

        <div className="mobile-priority-summary">
          <div>
            <span>现价</span>
            <strong>{formatPrice(item.latest_price)}</strong>
            <small>{formatPct(item.change_pct)}</small>
          </div>
          <div>
            <span>买点区</span>
            <strong>{formatPrice(item.entry_zone_low)}-{formatPrice(item.entry_zone_high)}</strong>
            <small>止损 {formatPrice(item.stop_loss)}</small>
          </div>
          <div>
            <span>策略</span>
            <strong>{strategies}</strong>
            <small>{mainline}</small>
          </div>
        </div>

        <div className="mobile-priority-plan">
          <strong>现在怎么做</strong>
          <p>{item.next_action_text || item.action_summary || "只在买点区和确认条件同时满足时处理，不追高。"}</p>
        </div>

        <div className="mobile-app-sheet-actions">
          <button
            type="button"
            className="mobile-app-secondary"
            onClick={() => {
              onMarkBought(item)
              onClose()
            }}
          >
            记为持仓
          </button>
          <button
            type="button"
            className="mobile-app-primary"
            onClick={() => {
              void onOpenDetail(item.symbol)
              onClose()
            }}
          >
            查看详情
          </button>
        </div>
      </section>
    </div>
  )
}

export function MobilePaperOrderSheet({
  open,
  loading,
  defaultSymbol,
  defaultName,
  defaultPrice,
  onClose,
  onSubmit
}: {
  open: boolean
  loading: boolean
  defaultSymbol?: string
  defaultName?: string
  defaultPrice?: number | null
  onClose: () => void
  onSubmit: (payload: PaperOrderCreate) => Promise<boolean> | boolean
}) {
  const [symbol, setSymbol] = useState("")
  const [name, setName] = useState("")
  const [side, setSide] = useState<PaperOrderCreate["side"]>("buy")
  const [orderType, setOrderType] = useState<NonNullable<PaperOrderCreate["order_type"]>>("market")
  const [quantity, setQuantity] = useState("100")
  const [price, setPrice] = useState("")
  const [formError, setFormError] = useState("")

  useEffect(() => {
    if (!open) {
      return
    }
    setSymbol(defaultSymbol ?? "")
    setName(defaultName ?? "")
    setSide("buy")
    setOrderType("market")
    setQuantity("100")
    setPrice(typeof defaultPrice === "number" && Number.isFinite(defaultPrice) ? String(defaultPrice) : "")
    setFormError("")
  }, [defaultName, defaultPrice, defaultSymbol, open])

  if (!open) {
    return null
  }

  async function handleSubmit() {
    const normalizedSymbol = symbol.trim().toUpperCase()
    const numericQuantity = Number.parseInt(quantity, 10)
    const numericPrice = Number.parseFloat(price)

    if (!normalizedSymbol) {
      setFormError("代码必填")
      return
    }
    if (!Number.isFinite(numericQuantity) || numericQuantity <= 0 || numericQuantity % 100 !== 0) {
      setFormError("数量必须是 100 的正整数倍")
      return
    }
    if (orderType === "limit" && (!Number.isFinite(numericPrice) || numericPrice <= 0)) {
      setFormError("限价委托必须填写有效价格")
      return
    }

    setFormError("")
    const ok = await onSubmit({
      symbol: normalizedSymbol,
      name: name.trim() || normalizedSymbol,
      side,
      order_type: orderType,
      quantity: numericQuantity,
      price: orderType === "limit" ? numericPrice : null,
      current_price: Number.isFinite(numericPrice) && numericPrice > 0 ? numericPrice : null,
      source: "mobile_manual",
      reason: "App 端手动模拟委托"
    })
    if (ok) {
      onClose()
    }
  }

  return (
    <div className="mobile-app-sheet-backdrop" role="presentation" onClick={onClose}>
      <section className="mobile-app-sheet mobile-paper-order-sheet" onClick={(event) => event.stopPropagation()}>
        <div className="mobile-app-sheet-head">
          <div className="mobile-app-sheet-title">
            <h2>模拟委托</h2>
            <small>仅记录模拟交易，不代表真实委托</small>
          </div>
          <button type="button" className="mobile-app-icon-button" onClick={onClose} aria-label="关闭">
            <Icon name="close" />
          </button>
        </div>

        <div className="mobile-paper-order-form">
          <label>
            <span>代码</span>
            <input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} placeholder="510300" />
          </label>
          <label>
            <span>名称</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="可选" />
          </label>
          <div className="mobile-paper-order-segment">
            <button type="button" className={side === "buy" ? "active" : ""} onClick={() => setSide("buy")}>买入</button>
            <button type="button" className={side === "sell" ? "active" : ""} onClick={() => setSide("sell")}>卖出</button>
          </div>
          <div className="mobile-paper-order-segment">
            <button type="button" className={orderType === "market" ? "active" : ""} onClick={() => setOrderType("market")}>市价</button>
            <button type="button" className={orderType === "limit" ? "active" : ""} onClick={() => setOrderType("limit")}>限价</button>
          </div>
          <label>
            <span>数量</span>
            <input inputMode="numeric" value={quantity} onChange={(event) => setQuantity(event.target.value)} placeholder="100" />
          </label>
          <label>
            <span>{orderType === "limit" ? "限价" : "参考价"}</span>
            <input inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value)} placeholder="可选" />
          </label>
          {formError ? <div className="mobile-paper-order-error">{formError}</div> : null}
        </div>

        <div className="mobile-app-sheet-actions">
          <button type="button" className="mobile-app-secondary" onClick={onClose}>取消</button>
          <button type="button" className="mobile-app-primary" disabled={loading} onClick={() => void handleSubmit()}>
            {loading ? "提交中" : "提交委托"}
          </button>
        </div>
      </section>
    </div>
  )
}

export function AiDecisionSheet({
  open,
  board,
  onClose
}: {
  open: boolean
  board: LowBuyPriorityBoardResult | null
  onClose: () => void
}) {
  if (!open) {
    return null
  }
  const top = board?.items?.[0]
  const canBuy = top?.buy_signal_state === "buy_now" || top?.buy_signal_state === "soft_buy_now"
    ? "只看确定买入或接近买点的前排，其他不提前买"
    : "没有确定买入，今天以观察和处理持仓为主"
  const why = top
    ? `前排是 ${top.name}，当前状态为 ${top.simple_bucket_text || top.buy_signal_text}。${top.next_action_text || ""}`
    : "当前榜单没有明确前排信号。"
  const risk = board?.portfolio_risk?.notes?.[0] || "最大风险是未到买点提前买，或跌破止损不退出。"
  const plan = "明天先看是否仍在买点区，冲高先减仓，跌破止损先退出。"

  return (
    <div className="mobile-app-sheet-backdrop" role="presentation" onClick={onClose}>
      <section className="mobile-app-sheet mobile-ai-sheet" onClick={(event) => event.stopPropagation()}>
        <div className="mobile-app-sheet-head">
          <div>
            <div className="mobile-app-sheet-title">
              <h2>榜单解读</h2>
              <small>只解释硬规则，不放宽买点</small>
            </div>
          </div>
          <button type="button" className="mobile-app-icon-button" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>
        <div className="mobile-ai-grid">
          <AiDecisionBlock title="能不能买" content={canBuy} />
          <AiDecisionBlock title="为什么" content={why} />
          <AiDecisionBlock title="最大风险" content={risk} />
          <AiDecisionBlock title="明天怎么处理" content={plan} />
        </div>
      </section>
    </div>
  )
}

function AiDecisionBlock({ title, content }: { title: string; content: string }) {
  return (
    <article className="mobile-ai-block">
      <strong>{title}</strong>
      <p>{content}</p>
    </article>
  )
}

export function AppUpdateSheet({
  updateInfo,
  onClose,
  onUpdate
}: {
  updateInfo: AppAndroidUpdateResponse | null
  onClose: () => void
  onUpdate: () => void | Promise<void>
}) {
  if (!updateInfo) {
    return null
  }

  return (
    <div className="mobile-app-sheet-backdrop" role="presentation" onClick={updateInfo.mandatory ? undefined : onClose}>
      <section className="mobile-app-sheet mobile-update-sheet" onClick={(event) => event.stopPropagation()}>
        <div className="mobile-app-sheet-head">
          <div className="mobile-app-sheet-title">
            <h2>{updateInfo.title || "发现新版本"}</h2>
            <small>最新版 {updateInfo.latest_version_name}</small>
          </div>
          {!updateInfo.mandatory ? (
            <button type="button" className="mobile-app-icon-button" onClick={onClose} aria-label="关闭">
              关闭
            </button>
          ) : null}
        </div>

        <div className="mobile-update-body">
          <p>{updateInfo.message}</p>
          {updateInfo.changelog.length ? (
            <ul>
              {updateInfo.changelog.slice(0, 5).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          <small>
            安装包 {Math.max(0.1, updateInfo.apk_size_bytes / 1024 / 1024).toFixed(1)} MB
            {updateInfo.mandatory ? " · 必须更新后继续使用" : ""}
          </small>
        </div>

        <div className="mobile-update-actions">
          {!updateInfo.mandatory ? (
            <button type="button" className="mobile-app-secondary" onClick={onClose}>
              稍后再说
            </button>
          ) : null}
          <button type="button" className="mobile-app-primary" onClick={() => void onUpdate()}>
            立即更新
          </button>
        </div>
      </section>
    </div>
  )
}
