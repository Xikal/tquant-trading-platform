import { startTransition, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { appApi } from "../api/appClient"
import { api } from "../api/client"
import { clearAuthTokens, getAuthAccessToken } from "../api/base"
import { HomeCard } from "../features/app-preview/components"
import {
  HoldingCard,
  type HoldingRowData,
  PriorityBoardCard
} from "../features/app-preview/portfolio"
import {
  HoldingEditorSheet,
  type HoldingEditorSeed
} from "../features/app-preview/holdingEditor"
import { useAppPreviewData } from "../features/app-preview/hooks"
import type {
  AppAndroidUpdateResponse,
  AuthUser,
  LowBuyPriorityBoardItem,
  LowBuyPriorityBoardResult,
  PaperAccount,
  PaperGroupedPerformance,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperTrade,
  WatchlistItem
} from "../types"
import {
  formatAmount,
  Icon,
  LowBuyDetailSheet,
  MarketPulse,
  SegmentTabs,
  StatStrip
} from "./mobileSections"
import { useNativeRuntime } from "./useNativeRuntime"
import { useAppUpdate } from "./useAppUpdate"
import type { PaperOrderDraft } from "../features/trading-workspace/workspaceTypes"
import {
  formatAmount as formatPaperAmount,
  formatNumber,
  formatPct,
  formatPrice,
  nullableNumber,
  parseNumber
} from "../features/trading-workspace/workspaceFormatters"

type HomePanelTab = "watch" | "holdings"
type MobileTab = "home" | "low_buy" | "paper"

interface HoldingEditorState {
  mode: "create" | "buy" | "edit"
  seed: HoldingEditorSeed
}

function hasHolding(item: WatchlistItem) {
  return item.base_position > 0 || item.available_position > 0
}

function createSeedFromWatchlist(item: WatchlistItem): HoldingEditorSeed {
  return {
    symbol: item.symbol,
    name: item.name,
    base_position: item.base_position,
    available_position: item.available_position,
    cost_basis: item.cost_basis ?? null,
    memo: item.memo
  }
}

function createSeedFromBoardItem(
  item: LowBuyPriorityBoardItem,
  existing?: WatchlistItem
): HoldingEditorSeed {
  if (existing) {
    return createSeedFromWatchlist(existing)
  }

  return {
    symbol: item.symbol,
    name: item.name,
    base_position: 100,
    available_position: 0,
    cost_basis: item.latest_price,
    memo: "来自全策略优先级榜"
  }
}

function createSeedFromDetail(symbol: string, name: string, price: number, existing?: WatchlistItem): HoldingEditorSeed {
  if (existing) {
    return createSeedFromWatchlist(existing)
  }

  return {
    symbol,
    name,
    base_position: 100,
    available_position: 0,
    cost_basis: price,
    memo: "来自选股宝典"
  }
}

function MobileAuthScreen({
  loading,
  error,
  onSubmit
}: {
  loading: boolean
  error: string
  onSubmit: (payload: { username: string; password: string; register: boolean }) => Promise<void>
}) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [register, setRegister] = useState(false)
  const [formError, setFormError] = useState("")

  async function handleSubmit() {
    const nextUsername = username.trim()
    if (nextUsername.length < 3) {
      setFormError("账号至少 3 位")
      return
    }
    if (password.length < 6) {
      setFormError("密码至少 6 位")
      return
    }
    setFormError("")
    await onSubmit({ username: nextUsername, password, register })
  }

  return (
    <div className="mobile-app-shell mobile-auth-shell">
      <section className="mobile-auth-card">
        <div className="mobile-auth-head">
          <small>WEIS QUANT</small>
          <h1>维斯量化交易平台</h1>
          <p>登录后持仓和自选只保存在你的账号下，行情与策略结果仍共享同一套后端。</p>
        </div>

        <label className="mobile-auth-field">
          <span>账号</span>
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="输入用户名"
            autoCapitalize="none"
          />
        </label>

        <label className="mobile-auth-field">
          <span>密码</span>
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="至少 6 位"
            type="password"
          />
        </label>

        {formError || error ? <div className="mobile-app-error">{formError || error}</div> : null}

        <button type="button" className="mobile-app-primary mobile-auth-submit" onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? "处理中" : register ? "注册并登录" : "登录"}
        </button>

        <button type="button" className="mobile-auth-switch" onClick={() => setRegister((value) => !value)}>
          {register ? "已有账号，直接登录" : "没有账号，创建一个"}
        </button>
      </section>
    </div>
  )
}

export default function MobileApp() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState("")
  const [activeTab, setActiveTab] = useState<MobileTab>("home")
  const appUpdate = useAppUpdate()
  const {
    bootstrap,
    home,
    watchlist,
    priorityBoard,
    loading,
    actionLoading,
    detail,
    error,
    message,
    pulseTime,
    priorityPulseTime,
    setActiveTab: setPreviewTab,
    setDetail,
    refreshActiveTab,
    openCandidate,
    saveHolding,
    removeWatchItem
  } = useAppPreviewData("first_board", Boolean(authUser))
  const [homePanelTab, setHomePanelTab] = useState<HomePanelTab>("watch")
  const [holdingEditor, setHoldingEditor] = useState<HoldingEditorState | null>(null)
  const [aiOpen, setAiOpen] = useState(false)
  const [paperAccount, setPaperAccount] = useState<PaperAccount | null>(null)
  const [paperPositions, setPaperPositions] = useState<PaperPosition[]>([])
  const [paperOrders, setPaperOrders] = useState<PaperOrder[]>([])
  const [paperTrades, setPaperTrades] = useState<PaperTrade[]>([])
  const [paperPerformance, setPaperPerformance] = useState<PaperPerformance | null>(null)
  const [paperStrategyPerformance, setPaperStrategyPerformance] = useState<PaperGroupedPerformance[]>([])
  const [paperMarketPerformance, setPaperMarketPerformance] = useState<PaperGroupedPerformance[]>([])
  const [paperLoading, setPaperLoading] = useState("")
  const [paperError, setPaperError] = useState("")
  const [paperMessage, setPaperMessage] = useState("")
  const [paperDraft, setPaperDraft] = useState<PaperOrderDraft>({
    symbol: "",
    name: "",
    side: "buy",
    order_type: "market",
    quantity: "100",
    price: "",
    current_price: "",
    strategy_key: "",
    reason: "",
    require_intraday_confirmation: false
  })
  const { isOnline } = useNativeRuntime(() => {
    startTransition(() => {
      void refreshActiveTab()
      void appUpdate.checkForUpdate()
    })
  })

  const watchlistItems = watchlist?.items ?? []
  const watchlistMap = useMemo(
    () => new Map(watchlistItems.map((item) => [item.symbol, item])),
    [watchlistItems]
  )
  const homeMap = useMemo(
    () => new Map((home?.items ?? []).map((item) => [item.symbol, item])),
    [home?.items]
  )

  const holdingRows = useMemo<HoldingRowData[]>(() => {
    return watchlistItems
      .filter(hasHolding)
      .map((record) => {
        const liveCard = homeMap.get(record.symbol) ?? null
        const livePrice = liveCard?.quote.last_price ?? null
        const marketValue =
          typeof livePrice === "number" ? livePrice * record.base_position : null
        const floatingPnL =
          typeof livePrice === "number" && typeof record.cost_basis === "number"
            ? (livePrice - record.cost_basis) * record.base_position
            : null
        const floatingPnLPct =
          typeof livePrice === "number" &&
          typeof record.cost_basis === "number" &&
          record.cost_basis > 0
            ? ((livePrice - record.cost_basis) / record.cost_basis) * 100
            : null

        return {
          record,
          quote: liveCard?.quote ?? null,
          marketValue,
          floatingPnL,
          floatingPnLPct,
          plainActionText: liveCard?.plain_action_text,
          plainActionReason: liveCard?.plain_action_reason,
          plainExecutionText: liveCard?.plain_execution_text,
          plainInvalidCondition: liveCard?.plain_invalid_condition
        }
      })
  }, [homeMap, watchlistItems])

  const holdingsSummary = useMemo(() => {
    const totalMarketValue = holdingRows.reduce(
      (sum, row) => sum + (row.marketValue ?? 0),
      0
    )
    const totalFloatingPnL = holdingRows.reduce(
      (sum, row) => sum + (row.floatingPnL ?? 0),
      0
    )
    return {
      count: holdingRows.length,
      totalMarketValue,
      totalFloatingPnL
    }
  }, [holdingRows])

  const priorityBoardItems = priorityBoard?.items ?? []

  const homeStrip =
    homePanelTab === "watch"
      ? [
          {
            label: "监控总数",
            value: String(home?.summary.total ?? 0),
            change: `执行 ${(home?.summary.positive_t_count ?? 0) + (home?.summary.negative_t_count ?? 0)}`,
            tone: "positive" as const
          },
          {
            label: "观望标的",
            value: String(home?.summary.hold_count ?? 0),
            change: `高风险 ${home?.summary.high_risk_count ?? 0}`,
            tone: "neutral" as const
          },
          {
            label: "刷新时间",
            value: pulseTime,
            change: isOnline ? "在线" : "离线",
            tone: isOnline ? ("positive" as const) : ("negative" as const)
          }
        ]
      : [
          {
            label: "持仓股",
            value: String(holdingsSummary.count),
            change: `监控 ${watchlistItems.length}`,
            tone: "neutral" as const
          },
          {
            label: "总市值",
            value: formatAmount(holdingsSummary.totalMarketValue),
            change: "按现价计算",
            tone: "neutral" as const
          },
          {
            label: "浮动盈亏",
            value: formatAmount(holdingsSummary.totalFloatingPnL),
            change: holdingsSummary.totalFloatingPnL >= 0 ? "盈利" : "回撤",
            tone: holdingsSummary.totalFloatingPnL >= 0 ? ("positive" as const) : ("negative" as const)
          }
        ]

  const lowBuyStrip = [
    {
      label: "榜单数",
      value: String(priorityBoardItems.length),
      change: `总候选 ${priorityBoard?.total_candidates ?? 0}`,
      tone: "positive" as const
    },
    {
      label: "主看机会",
      value: String(priorityBoard?.immediate_count ?? 0),
      change: `重点观察 ${priorityBoard?.focus_count ?? 0}`,
      tone: (priorityBoard?.immediate_count ?? 0) > 0 ? ("positive" as const) : ("neutral" as const)
    },
    {
      label: "更新时间",
      value: priorityPulseTime,
      change: `仅跟踪 ${priorityBoard?.track_count ?? 0}`,
      tone: "neutral" as const
    }
  ]

  function openCreateHolding() {
    setHoldingEditor({
      mode: "create",
      seed: {
        symbol: "",
        name: "",
        base_position: 100,
        available_position: 0,
        cost_basis: null,
        memo: ""
      }
    })
  }

  function openEditHolding(item: WatchlistItem) {
    setHoldingEditor({
      mode: "edit",
      seed: createSeedFromWatchlist(item)
    })
  }

  function openBoughtEditor(item: LowBuyPriorityBoardItem) {
    setHoldingEditor({
      mode: watchlistMap.has(item.symbol) ? "edit" : "buy",
      seed: createSeedFromBoardItem(item, watchlistMap.get(item.symbol))
    })
  }

  function openDetailHoldingEditor() {
    if (!detail) {
      return
    }
    setHoldingEditor({
      mode: watchlistMap.has(detail.candidate.symbol) ? "edit" : "buy",
      seed: createSeedFromDetail(
        detail.candidate.symbol,
        detail.candidate.name,
        detail.candidate.latest_price,
        watchlistMap.get(detail.candidate.symbol)
      )
    })
    setDetail(null)
  }

  async function handleSubmitHolding(payload: Omit<WatchlistItem, "created_at">) {
    const mode = holdingEditor?.mode ?? "edit"
    const success = await saveHolding(
      payload,
      mode === "buy" ? `${payload.symbol} 已入持仓` : "持仓已更新"
    )
    if (success) {
      setHoldingEditor(null)
    }
  }

  async function handleRemoveWatchItem(symbol: string) {
    return removeWatchItem(symbol)
  }

  async function handleRemoveHolding(item: WatchlistItem) {
    const success = await removeWatchItem(item.symbol)
    if (success) {
      setHoldingEditor(null)
    }
  }

  function handleSwitchTab(nextTab: MobileTab) {
    setHoldingEditor(null)
    setDetail(null)
    setActiveTab(nextTab)
    if (nextTab !== "paper") {
      setPreviewTab(nextTab)
    }
  }

  const isDetailInWatchlist = detail ? watchlistMap.has(detail.candidate.symbol) : false

  useEffect(() => {
    if (!getAuthAccessToken()) {
      setAuthLoading(false)
      return
    }
    const loadMe = () => appApi.getMe()
    loadMe()
      .then((payload) => {
        setAuthUser(payload.user)
        setAuthError("")
      })
      .catch(async () => {
        try {
          const refreshed = await appApi.refreshAuth()
          setAuthUser(refreshed.user)
          setAuthError("")
        } catch (err) {
          clearAuthTokens()
          setAuthError(err instanceof Error ? err.message : "登录已失效")
        }
      })
      .finally(() => {
        setAuthLoading(false)
      })
  }, [])

  async function handleAuthSubmit(payload: { username: string; password: string; register: boolean }) {
    try {
      setAuthLoading(true)
      setAuthError("")
      const result = payload.register
        ? await appApi.register({
            username: payload.username,
            password: payload.password,
            display_name: payload.username,
            device_name: "mobile-app"
          })
        : await appApi.login({
            username: payload.username,
            password: payload.password,
            device_name: "mobile-app"
          })
      setAuthUser(result.user)
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "登录失败")
    } finally {
      setAuthLoading(false)
    }
  }

  async function handleLogout() {
    await appApi.logout()
    setAuthUser(null)
    setAuthError("")
  }

  async function loadPaper() {
    try {
      setPaperLoading("paper")
      setPaperError("")
      const [
        accountResult,
        positionsResult,
        ordersResult,
        tradesResult,
        performanceResult,
        strategyResult,
        marketResult
      ] = await Promise.allSettled([
        api.getPaperAccount(),
        api.getPaperPositions(),
        api.getPaperOrders(80),
        api.getPaperTrades(80),
        api.getPaperPerformance(),
        api.getPaperPerformanceByStrategy(),
        api.getPaperPerformanceByMarketState()
      ])
      if (accountResult.status === "fulfilled") setPaperAccount(accountResult.value)
      if (positionsResult.status === "fulfilled") setPaperPositions(positionsResult.value.positions)
      if (ordersResult.status === "fulfilled") setPaperOrders(ordersResult.value)
      if (tradesResult.status === "fulfilled") setPaperTrades(tradesResult.value.trades)
      if (performanceResult.status === "fulfilled") setPaperPerformance(performanceResult.value)
      if (strategyResult.status === "fulfilled") setPaperStrategyPerformance(strategyResult.value)
      if (marketResult.status === "fulfilled") setPaperMarketPerformance(marketResult.value)
      const rejected = [accountResult, positionsResult, ordersResult, tradesResult, performanceResult, strategyResult, marketResult]
        .find((result): result is PromiseRejectedResult => result.status === "rejected")
      if (rejected) {
        setPaperError(rejected.reason instanceof Error ? rejected.reason.message : "模拟盘加载失败")
      }
    } finally {
      setPaperLoading("")
    }
  }

  async function refreshPaperQuotes() {
    try {
      setPaperLoading("paper-quotes")
      setPaperError("")
      const result = await api.refreshPaperPositions()
      setPaperPositions(result.positions)
      const [accountResult, performanceResult] = await Promise.allSettled([
        api.getPaperAccount(),
        api.getPaperPerformance()
      ])
      if (accountResult.status === "fulfilled") setPaperAccount(accountResult.value)
      if (performanceResult.status === "fulfilled") setPaperPerformance(performanceResult.value)
      setPaperMessage("持仓价格已刷新")
    } catch (err) {
      setPaperError(err instanceof Error ? err.message : "刷新失败")
    } finally {
      setPaperLoading("")
    }
  }

  async function togglePaperPause() {
    try {
      setPaperLoading("paper-status")
      const nextAccount = paperAccount?.status === "paused"
        ? await api.resumePaperAccount()
        : await api.pausePaperAccount()
      setPaperAccount(nextAccount)
      setPaperMessage(nextAccount.status === "paused" ? "模拟盘已暂停" : "模拟盘已恢复")
    } catch (err) {
      setPaperError(err instanceof Error ? err.message : "状态切换失败")
    } finally {
      setPaperLoading("")
    }
  }

  async function submitPaperOrder() {
    try {
      setPaperLoading("paper-order")
      setPaperError("")
      const symbol = paperDraft.symbol.trim()
      const quantity = parseNumber(paperDraft.quantity)
      if (!symbol) throw new Error("请填写代码")
      if (quantity <= 0 || quantity % 100 !== 0) throw new Error("数量必须是 100 股整数倍")
      const result = await api.createPaperOrder({
        symbol,
        name: paperDraft.name.trim(),
        side: paperDraft.side,
        order_type: paperDraft.order_type,
        quantity,
        price: nullableNumber(paperDraft.price),
        current_price: nullableNumber(paperDraft.current_price),
        strategy_key: paperDraft.strategy_key.trim(),
        reason: paperDraft.reason.trim(),
        require_intraday_confirmation: paperDraft.require_intraday_confirmation,
        source: "mobile"
      })
      setPaperMessage(result.status === "filled" ? "模拟委托已成交" : result.reject_reason || "模拟委托已提交")
      await loadPaper()
    } catch (err) {
      setPaperError(err instanceof Error ? err.message : "提交失败")
    } finally {
      setPaperLoading("")
    }
  }

  useEffect(() => {
    if (authUser && activeTab === "paper" && !paperAccount && !paperLoading) {
      void loadPaper()
    }
  }, [activeTab, authUser, paperAccount, paperLoading])

  if (!authUser) {
    return (
      <MobileAuthScreen
        loading={authLoading}
        error={authError}
        onSubmit={handleAuthSubmit}
      />
    )
  }

  return (
    <div className="mobile-app-shell">
      <header className="mobile-app-topbar">
        <div>
          <small className="mobile-app-kicker">{bootstrap?.app_name ?? "A股短线做T助手"}</small>
          <h1>{activeTab === "home" ? "实时监控" : activeTab === "low_buy" ? "选股宝典" : "模拟盘"}</h1>
        </div>
        <div className="mobile-app-topbar-meta">
          {activeTab === "home" ? (
            <>
              <button type="button" className="mobile-app-icon-button" onClick={() => void refreshActiveTab()}>
                <Icon name="refresh" />
                <span>刷新</span>
              </button>
              <span className="mobile-app-time">{pulseTime}</span>
              <button type="button" className="mobile-app-icon-button" onClick={() => void handleLogout()}>
                <span>退出</span>
              </button>
            </>
          ) : activeTab === "paper" ? (
            <>
              <button type="button" className="mobile-app-icon-button" onClick={() => void loadPaper()}>
                <Icon name="refresh" />
                <span>刷新</span>
              </button>
              <button type="button" className="mobile-app-icon-button" onClick={() => void refreshPaperQuotes()}>
                <span>刷新价格</span>
              </button>
              <button type="button" className="mobile-app-icon-button" onClick={() => void handleLogout()}>
                <span>退出</span>
              </button>
            </>
          ) : (
            <>
              <button type="button" className="mobile-app-icon-button" aria-label="搜索">
                <Icon name="search" />
              </button>
              <button type="button" className="mobile-app-icon-button" aria-label="筛选">
                <Icon name="filter" />
              </button>
              <button type="button" className="mobile-app-icon-button" onClick={() => void handleLogout()}>
                <span>退出</span>
              </button>
            </>
          )}
        </div>
      </header>

      {message ? <div className="mobile-app-banner">{message}</div> : null}
      {error ? <div className="mobile-app-error">{error}</div> : null}
      {activeTab === "paper" && paperMessage ? <div className="mobile-app-banner">{paperMessage}</div> : null}
      {activeTab === "paper" && paperError ? <div className="mobile-app-error">{paperError}</div> : null}

      <main className="mobile-app-body">
        {activeTab === "home" ? (
          <>
            <StatStrip items={homeStrip} />
            <SegmentTabs
              items={[
                { key: "watch", label: "监控", active: homePanelTab === "watch" },
                { key: "holdings", label: "持仓股", active: homePanelTab === "holdings" }
              ]}
              onChange={(key) => setHomePanelTab(key as HomePanelTab)}
            />

            {homePanelTab === "watch" ? (
              <>
                <div className="mobile-app-list-toolbar">
                  <strong>全部监控 ({home?.summary.total ?? 0})</strong>
                  <small>价 / 信号 / 分</small>
                </div>

                <section className="mobile-app-list">
                  {(home?.items ?? []).map((item) => (
                    <HomeCard
                      key={item.symbol}
                      item={item}
                      compact
                      onRemove={() => handleRemoveWatchItem(item.symbol)}
                    />
                  ))}
                  {!loading && !(home?.items.length ?? 0) ? (
                    <div className="mobile-app-empty">当前没有监控股</div>
                  ) : null}
                </section>
              </>
            ) : (
              <>
                <div className="mobile-app-list-toolbar mobile-app-list-toolbar-actions">
                  <strong>持仓股 ({holdingRows.length})</strong>
                  <button type="button" className="mobile-inline-action" onClick={openCreateHolding}>
                    新增
                  </button>
                </div>

                <section className="mobile-app-list">
                  {holdingRows.map((row) => (
                    <HoldingCard
                      key={row.record.symbol}
                      row={row}
                      onEdit={openEditHolding}
                      onRemove={handleRemoveHolding}
                    />
                  ))}
                  {!loading && !holdingRows.length ? (
                    <div className="mobile-app-empty">当前没有持仓股</div>
                  ) : null}
                </section>
              </>
            )}
          </>
        ) : activeTab === "low_buy" ? (
          <>
            <StatStrip items={lowBuyStrip} />
            <MarketPulse board={priorityBoard} />

            <div className="mobile-app-list-toolbar">
              <strong>全策略优先级榜</strong>
              <button type="button" className="mobile-inline-action" onClick={() => setAiOpen(true)}>
                解读榜单
              </button>
            </div>

            <section className="mobile-app-list">
              {priorityBoardItems.map((item, index) => (
                <PriorityBoardCard
                  key={item.symbol}
                  item={item}
                  rank={index + 1}
                  inWatchlist={watchlistMap.has(item.symbol)}
                  onOpen={openCandidate}
                  onBought={openBoughtEditor}
                />
              ))}
              {!loading && !priorityBoardItems.length ? (
                <div className="mobile-app-empty">当前没有榜单数据</div>
              ) : null}
            </section>
          </>
        ) : (
          <MobilePaperPanel
            account={paperAccount}
            positions={paperPositions}
            orders={paperOrders}
            trades={paperTrades}
            performance={paperPerformance}
            strategyPerformance={paperStrategyPerformance}
            marketPerformance={paperMarketPerformance}
            draft={paperDraft}
            loading={paperLoading}
            onDraftChange={setPaperDraft}
            onRefresh={loadPaper}
            onRefreshQuotes={refreshPaperQuotes}
            onTogglePause={togglePaperPause}
            onSubmitOrder={submitPaperOrder}
          />
        )}
      </main>

      <nav className="mobile-app-tabbar" aria-label="移动端导航">
        <button
          type="button"
          className={activeTab === "home" ? "active" : ""}
          onClick={() => handleSwitchTab("home")}
        >
          <span>实时监控</span>
        </button>
        <button
          type="button"
          className={activeTab === "low_buy" ? "active" : ""}
          onClick={() => handleSwitchTab("low_buy")}
        >
          <span>选股宝典</span>
        </button>
        <button
          type="button"
          className={activeTab === "paper" ? "active" : ""}
          onClick={() => handleSwitchTab("paper")}
        >
          <span>模拟盘</span>
        </button>
      </nav>

      <LowBuyDetailSheet
        detail={detail}
        inWatchlist={isDetailInWatchlist}
        onClose={() => setDetail(null)}
        onMarkBought={openDetailHoldingEditor}
      />

      <HoldingEditorSheet
        open={Boolean(holdingEditor)}
        seed={
          holdingEditor?.seed ?? {
            symbol: "",
            name: "",
            base_position: 0,
            available_position: 0,
            cost_basis: null,
            memo: ""
          }
        }
        mode={holdingEditor?.mode ?? "create"}
        saving={actionLoading}
        onClose={() => setHoldingEditor(null)}
        onSubmit={handleSubmitHolding}
      />

      <AppUpdateSheet
        updateInfo={appUpdate.updateInfo}
        onClose={appUpdate.dismissUpdate}
        onUpdate={appUpdate.openUpdate}
      />

      <AiDecisionSheet
        open={aiOpen}
        board={priorityBoard}
        onClose={() => setAiOpen(false)}
      />
    </div>
  )
}

function MobilePaperPanel({
  account,
  positions,
  orders,
  trades,
  performance,
  strategyPerformance,
  marketPerformance,
  draft,
  loading,
  onDraftChange,
  onRefresh,
  onRefreshQuotes,
  onTogglePause,
  onSubmitOrder
}: {
  account: PaperAccount | null
  positions: PaperPosition[]
  orders: PaperOrder[]
  trades: PaperTrade[]
  performance: PaperPerformance | null
  strategyPerformance: PaperGroupedPerformance[]
  marketPerformance: PaperGroupedPerformance[]
  draft: PaperOrderDraft
  loading: string
  onDraftChange: (draft: PaperOrderDraft) => void
  onRefresh: () => void | Promise<void>
  onRefreshQuotes: () => void | Promise<void>
  onTogglePause: () => void | Promise<void>
  onSubmitOrder: () => void | Promise<void>
}) {
  const paused = account?.status === "paused"
  const metrics = [
    { label: "总资产", value: formatPaperAmount(account?.total_assets), tone: "neutral" as const },
    { label: "可用资金", value: formatPaperAmount(account?.cash_available), tone: "neutral" as const },
    { label: "持仓市值", value: formatPaperAmount(account?.market_value), tone: "neutral" as const },
    { label: "浮动盈亏", value: formatNumber(account?.unrealized_pnl), tone: paperTone(account?.unrealized_pnl) },
    { label: "总收益率", value: formatPct(performance?.total_return_pct), tone: paperTone(performance?.total_return_pct) },
    { label: "状态", value: account ? (paused ? "已暂停" : "运行中") : "--", tone: paused ? ("warning" as const) : ("negative" as const) }
  ]

  return (
    <>
      <section className="mobile-paper-hero">
        <div>
          <strong>模拟盘</strong>
          <small>记录策略执行效果，不代表真实交易指令</small>
        </div>
        <button type="button" className="mobile-inline-action" onClick={() => void onTogglePause()} disabled={Boolean(loading)}>
          {paused ? "恢复模拟" : "暂停模拟"}
        </button>
      </section>

      <section className="mobile-paper-metrics">
        {metrics.map((item) => (
          <article key={item.label} className={`mobile-paper-metric tone-${item.tone}`}>
            <small>{item.label}</small>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>

      <section className={`mobile-paper-card mobile-paper-order${paused ? " paused" : ""}`}>
        <div className="mobile-paper-section-head">
          <strong>录入模拟委托</strong>
          <button type="button" className="mobile-inline-action" onClick={() => void onRefreshQuotes()} disabled={Boolean(loading)}>
            刷新价格
          </button>
        </div>
        <div className="mobile-paper-form-grid">
          <PaperField label="代码" value={draft.symbol} onChange={(value) => onDraftChange({ ...draft, symbol: value })} />
          <PaperField label="名称" value={draft.name} onChange={(value) => onDraftChange({ ...draft, name: value })} />
          <label>
            <span>方向</span>
            <select value={draft.side} onChange={(event) => onDraftChange({ ...draft, side: event.target.value as "buy" | "sell" })}>
              <option value="buy">买入</option>
              <option value="sell">卖出</option>
            </select>
          </label>
          <label>
            <span>类型</span>
            <select value={draft.order_type} onChange={(event) => onDraftChange({ ...draft, order_type: event.target.value as "market" | "limit" })}>
              <option value="market">市价</option>
              <option value="limit">限价</option>
            </select>
          </label>
          <PaperField label="数量" value={draft.quantity} placeholder="100 股整数倍" onChange={(value) => onDraftChange({ ...draft, quantity: value })} />
          <PaperField label="限价" value={draft.price} placeholder="限价单必填" onChange={(value) => onDraftChange({ ...draft, price: value })} />
          <PaperField label="现价" value={draft.current_price} onChange={(value) => onDraftChange({ ...draft, current_price: value })} />
          <PaperField label="策略" value={draft.strategy_key} placeholder="first_board" onChange={(value) => onDraftChange({ ...draft, strategy_key: value })} />
        </div>
        <PaperField label="执行理由" value={draft.reason} onChange={(value) => onDraftChange({ ...draft, reason: value })} />
        <button type="button" className="mobile-app-primary mobile-paper-submit" onClick={() => void onSubmitOrder()} disabled={loading === "paper-order"}>
          {loading === "paper-order" ? "提交中" : "提交模拟委托"}
        </button>
      </section>

      <section className="mobile-paper-card">
        <div className="mobile-paper-section-head">
          <strong>模拟持仓</strong>
          <small>{positions.length} 只 · 可滑动</small>
        </div>
        <div className="mobile-paper-scroll mobile-paper-position-scroll">
          {positions.length ? positions.map((item) => <MobilePaperPosition key={item.id} item={item} />) : <div className="mobile-app-empty">暂无模拟持仓</div>}
        </div>
      </section>

      <MobilePaperList title="委托记录" hint="最多显示 3 条">
        {orders.length ? orders.map((item) => <MobilePaperOrder key={item.id} item={item} />) : <div className="mobile-app-empty">暂无委托</div>}
      </MobilePaperList>

      <MobilePaperList title="成交与绩效" hint="最多显示 3 条" lead={<MobilePaperPerformancePills performance={performance} />}>
        {trades.length ? trades.map((item) => <MobilePaperTrade key={item.id} item={item} />) : <div className="mobile-app-empty">暂无成交</div>}
      </MobilePaperList>

      <MobilePaperPerformanceTable title="策略绩效" items={strategyPerformance} emptyText="暂无策略绩效" />
      <MobilePaperPerformanceTable title="市场状态绩效" items={marketPerformance} emptyText="暂无市场状态绩效" />
    </>
  )
}

function PaperField({ label, value, placeholder, onChange }: { label: string; value: string; placeholder?: string; onChange: (value: string) => void }) {
  return (
    <label>
      <span>{label}</span>
      <input value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

function MobilePaperPosition({ item }: { item: PaperPosition }) {
  const tone = item.latest_price == null ? "neutral" : paperTone(item.unrealized_pnl_pct)
  return (
    <article className={`mobile-paper-position tone-${tone}`}>
      <div>
        <strong>{item.name || item.symbol}</strong>
        <small>{item.symbol}</small>
      </div>
      <div className="mobile-paper-position-grid">
        <span>持仓 <b>{formatInteger(item.quantity)}</b></span>
        <span>可卖 <b>{formatInteger(item.available_quantity)}</b></span>
        <span>成本 <b>{formatPrice(item.cost_basis)}</b></span>
        <span>现价 <b>{formatPrice(item.latest_price)}</b></span>
      </div>
      <strong className={`mobile-paper-pnl tone-${tone}`}>{formatPct(item.unrealized_pnl_pct)}</strong>
    </article>
  )
}

function MobilePaperList({ title, hint, lead, children }: { title: string; hint: string; lead?: ReactNode; children: ReactNode }) {
  return (
    <section className="mobile-paper-card">
      <div className="mobile-paper-section-head">
        <strong>{title}</strong>
        <small>{hint}</small>
      </div>
      {lead}
      <div className="mobile-paper-scroll mobile-paper-three-scroll">{children}</div>
    </section>
  )
}

function MobilePaperOrder({ item }: { item: PaperOrder }) {
  return (
    <article className="mobile-paper-line mobile-paper-order-line">
      <strong>{item.symbol}</strong>
      <span>{item.order_type === "market" ? "市价" : "限价"}</span>
      <span>{paperOrderStatusText(item.status)}</span>
      <b>{formatInteger(item.quantity)} 股</b>
      <b>{formatPrice(item.avg_fill_price)}</b>
    </article>
  )
}

function MobilePaperTrade({ item }: { item: PaperTrade }) {
  return (
    <article className="mobile-paper-line mobile-paper-trade-line">
      <strong>{item.symbol}</strong>
      <span className={`tone-${item.side === "buy" ? "positive" : "negative"}`}>{item.side === "buy" ? "买入" : "卖出"}</span>
      <b>{formatInteger(item.quantity)} 股</b>
      <b>{formatPrice(item.price)}</b>
      <span>{formatMobileDateTime(item.trade_time)}</span>
    </article>
  )
}

function MobilePaperPerformancePills({ performance }: { performance: PaperPerformance | null }) {
  return (
    <div className="mobile-paper-pills">
      <span>成交 <b>{performance?.total_trades ?? 0}</b></span>
      <span>胜率 <b>{formatPct(performance?.win_rate_pct)}</b></span>
      <span>均收 <b className={`tone-${paperTone(performance?.avg_trade_return_pct)}`}>{formatPct(performance?.avg_trade_return_pct)}</b></span>
      <span>回撤 <b className={`tone-${paperTone(performance?.max_drawdown_pct)}`}>{formatPct(performance?.max_drawdown_pct)}</b></span>
    </div>
  )
}

function MobilePaperPerformanceTable({ title, items, emptyText }: { title: string; items: PaperGroupedPerformance[]; emptyText: string }) {
  return (
    <section className="mobile-paper-card">
      <div className="mobile-paper-section-head">
        <strong>{title}</strong>
        <small>最多显示 3 条</small>
      </div>
      <div className="mobile-paper-performance-head">
        <span>分组</span>
        <span>成交</span>
        <span>胜率</span>
        <span>均收</span>
        <span>PF</span>
      </div>
      <div className="mobile-paper-scroll mobile-paper-three-scroll">
        {items.length ? items.map((item) => (
          <article className="mobile-paper-performance-row" key={item.key || "未标注"}>
            <strong>{item.key || "未标注"}</strong>
            <span>{formatInteger(item.trades)}</span>
            <span>{formatPct(item.win_rate_pct)}</span>
            <span className={`tone-${paperTone(item.avg_return_pct)}`}>{formatPct(item.avg_return_pct)}</span>
            <span>{formatNumber(item.profit_factor)}</span>
          </article>
        )) : <div className="mobile-app-empty">{emptyText}</div>}
      </div>
    </section>
  )
}

function paperTone(value?: number | null): "positive" | "negative" | "neutral" | "warning" {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral"
  if (value > 0) return "positive"
  if (value < 0) return "negative"
  return "neutral"
}

function formatInteger(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--"
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })
}

function paperOrderStatusText(status: PaperOrder["status"]) {
  const map: Record<PaperOrder["status"], string> = {
    pending: "待成交",
    filled: "已成交",
    partial: "部分",
    rejected: "拒绝",
    cancelled: "撤销"
  }
  return map[status] ?? status
}

function formatMobileDateTime(value?: string | null) {
  if (!value) return "--"
  const match = value.replace("T", " ").match(/\d{2}:\d{2}:\d{2}/)
  return match?.[0] ?? value.slice(0, 16).replace("T", " ")
}

function AiDecisionSheet({
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

function AppUpdateSheet({
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
