import type { AuthUser } from "../types"
import { Button, NoticeBar, TabBar } from "antd-mobile"
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
            <Button fill="none" className="mobile-app-icon-button" onClick={onRefreshHome} aria-label="刷新">
              <Icon name="refresh" />
            </Button>
            <span className="mobile-app-time">{pulseTime}</span>
          </>
        ) : activeTab === "holdings" ? (
          <Button fill="none" className="mobile-app-icon-button" onClick={onRefreshHoldings} aria-label="刷新">
            <Icon name="refresh" />
          </Button>
        ) : (
          <Button fill="none" className="mobile-app-icon-button" onClick={onRefreshLowBuy} aria-label="刷新">
            <Icon name="refresh" />
          </Button>
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
      {signalToastVisible ? <NoticeBar className="mobile-app-notice" content="已发现信号" color="success" /> : null}
      {offline ? <NoticeBar className="mobile-app-notice" content="离线模式：正在显示最近缓存数据，恢复网络后会自动刷新。" color="alert" /> : null}
      {message ? <NoticeBar className="mobile-app-notice" content={message} color="info" /> : null}
      {error ? <NoticeBar className="mobile-app-notice" content={error} color="error" /> : null}
      {activeTab === "low_buy" && playbookError ? <NoticeBar className="mobile-app-notice" content={playbookError} color="error" /> : null}
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
    <TabBar
      className="mobile-app-tabbar mobile-app-adm-tabbar"
      activeKey={activeTab}
      onChange={(key) => onSwitchTab(key as MobileTab)}
      safeArea
    >
      <TabBar.Item key="home" title="实时监控" />
      <TabBar.Item key="holdings" title="持仓" />
      <TabBar.Item key="low_buy" title="选股宝典" />
    </TabBar>
  )
}
