import type {
  AppAndroidUpdateResponse,
  AuthUser,
  LowBuyPriorityBoardResult
} from "../types"
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
