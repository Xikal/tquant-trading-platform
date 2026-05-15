import type { AuthUser } from "../types"
import { AccountMenu } from "./MobileSheets"
import { Icon } from "./mobileSections"
import type { MobileTab } from "./mobileTypes"

function mobileTabTitle(activeTab: MobileTab) {
  if (activeTab === "home") return "实时监控"
  if (activeTab === "holdings") return "持仓"
  return "选股宝典"
}

export function MobileAppHeader({
  activeTab,
  pulseTime,
  user,
  accountMenuOpen,
  onRefreshHome,
  onRefreshHoldings,
  onRefreshLowBuy,
  onToggleAccountMenu,
  onOpenPreferences,
  onLogout
}: {
  activeTab: MobileTab
  pulseTime: string
  user: AuthUser
  accountMenuOpen: boolean
  onRefreshHome: () => void
  onRefreshHoldings: () => void
  onRefreshLowBuy: () => void
  onToggleAccountMenu: () => void
  onOpenPreferences: () => void
  onLogout: () => void
}) {
  return (
    <header className="mobile-app-topbar">
      <div>
        <h1>{mobileTabTitle(activeTab)}</h1>
      </div>
      <div className="mobile-app-topbar-meta">
        {activeTab === "home" ? (
          <>
            <button type="button" className="mobile-app-icon-button" onClick={onRefreshHome} aria-label="刷新">
              <Icon name="refresh" />
            </button>
            <span className="mobile-app-time">{pulseTime}</span>
          </>
        ) : activeTab === "holdings" ? (
          <button type="button" className="mobile-app-icon-button" onClick={onRefreshHoldings} aria-label="刷新">
            <Icon name="refresh" />
          </button>
        ) : (
          <button type="button" className="mobile-app-icon-button" onClick={onRefreshLowBuy} aria-label="刷新">
            <Icon name="refresh" />
          </button>
        )}
        <AccountMenu
          user={user}
          open={accountMenuOpen}
          onToggle={onToggleAccountMenu}
          onOpenPreferences={onOpenPreferences}
          onLogout={onLogout}
        />
      </div>
    </header>
  )
}

export function MobileStatusBanners({
  activeTab,
  signalToastVisible,
  offline,
  message,
  error,
  playbookError
}: {
  activeTab: MobileTab
  signalToastVisible: boolean
  offline: boolean
  message: string
  error: string
  playbookError: string
}) {
  return (
    <>
      {signalToastVisible ? <div className="mobile-app-signal-toast">已发现信号</div> : null}
      {offline ? <div className="mobile-app-banner">离线模式：正在显示最近缓存数据，恢复网络后会自动刷新。</div> : null}
      {message ? <div className="mobile-app-banner">{message}</div> : null}
      {error ? <div className="mobile-app-error">{error}</div> : null}
      {activeTab === "low_buy" && playbookError ? <div className="mobile-app-error">{playbookError}</div> : null}
    </>
  )
}

export function MobileTabBar({
  activeTab,
  onSwitchTab
}: {
  activeTab: MobileTab
  onSwitchTab: (tab: MobileTab) => void
}) {
  return (
    <nav className="mobile-app-tabbar" aria-label="移动端导航">
      <button
        type="button"
        className={activeTab === "home" ? "active" : ""}
        onClick={() => onSwitchTab("home")}
      >
        <span>实时监控</span>
      </button>
      <button
        type="button"
        className={activeTab === "holdings" ? "active" : ""}
        onClick={() => onSwitchTab("holdings")}
      >
        <span>持仓</span>
      </button>
      <button
        type="button"
        className={activeTab === "low_buy" ? "active" : ""}
        onClick={() => onSwitchTab("low_buy")}
      >
        <span>选股宝典</span>
      </button>
    </nav>
  )
}
