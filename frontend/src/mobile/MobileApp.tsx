import { startTransition, useEffect, useMemo, useRef, useState } from "react"
import { appApi } from "../api/appClient"
import { api } from "../api/client"
import { clearAuthTokens, getAuthAccessToken } from "../api/base"
import {
  HoldingEditorSheet,
  type HoldingEditorSeed
} from "../features/app-preview/holdingEditor"
import { useAppPreviewData } from "../features/app-preview/hooks"
import type {
  AppAndroidUpdateResponse,
  AuthUser,
  LowBuyCandidate,
  LowBuyPriorityBoardResult,
  LowBuyScreenerResult,
  PaperAccount,
  PaperGroupedPerformance,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperTrade,
  WatchlistItem
} from "../types"
import {
  Icon,
  LowBuyDetailSheet
} from "./mobileSections"
import { useNativeRuntime } from "./useNativeRuntime"
import { useAppUpdate } from "./useAppUpdate"
import { PaperTradingPanel } from "./PaperTradingPanel"
import {
  formatAmountCompact,
  MobileFocusCard,
  MobileHoldingStockCard,
  type MobileHoldingRowData,
  type MobileLowBuyCardItem,
  type MobileStrategyTabKey,
  MobileMarketPills,
  MobileMetricRow,
  MobilePriorityStockCard,
  MobileSectionTitle,
  MobileStrategyTabs,
  splitPriorityItems
} from "./MobileDesignCards"
import { buildHoldingSignalSignature, isHoldingTSignalActive } from "./holdingSignal"

type MobileTab = "home" | "holdings" | "low_buy" | "paper"

interface HoldingEditorState {
  mode: "create" | "buy" | "edit"
  seed: HoldingEditorSeed
}

function hasHolding(item: WatchlistItem) {
  return item.base_position > 0 || item.available_position > 0
}

function averageScore(values: Array<number | null | undefined>) {
  const validValues = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value))
  if (!validValues.length) {
    return "--"
  }
  return (validValues.reduce((sum, value) => sum + value, 0) / validValues.length / 10).toFixed(1)
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

function createSeedFromLowBuyItem(
  item: MobileLowBuyCardItem,
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
    memo: `来自${item.strategy_title || "选股宝典"}`
  }
}

function uniqueLowBuyCandidates(items: LowBuyCandidate[]) {
  const seen = new Set<string>()
  return items.filter((item) => {
    if (!item.symbol || seen.has(item.symbol)) {
      return false
    }
    seen.add(item.symbol)
    return true
  })
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
      <section className="mobile-auth-hero" aria-label="登录动效">
        <div className="mobile-auth-status">
          <span>9:41</span>
          <span>5G ▰▰▰ ◔</span>
        </div>
        <span className="mobile-auth-online">● 行情在线</span>
        <div className="mobile-auth-head">
          <small>WEIS QUANT</small>
          <h1>维斯量化 TQuant</h1>
          <p>盘中监控、选股宝典、模拟交易统一接入。</p>
        </div>
        <div className="mobile-auth-profit">
          <span>今日策略浮盈</span>
          <strong>+¥128,600</strong>
          <small>命中率 78% · 3 个可执行机会</small>
        </div>
        <div className="mobile-auth-bars" aria-hidden="true">
          <i /><i /><i /><i /><i /><i /><i />
        </div>
        <div className="mobile-auth-radar" aria-hidden="true" />
      </section>

      <section className="mobile-auth-card">
        <div className="mobile-auth-card-head">
          <h2>登录进入工作台</h2>
          <p>同步持仓监控、低吸候选与研究复盘</p>
        </div>

        <label className="mobile-auth-field">
          <span>手机号 / 账号</span>
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="请输入手机号或账号"
            autoCapitalize="none"
          />
        </label>

        <label className="mobile-auth-field">
          <span>登录密码</span>
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="请输入登录密码"
            type="password"
          />
        </label>

        {formError || error ? <div className="mobile-app-error">{formError || error}</div> : null}

        <div className="mobile-auth-row">
          <span>☑ 记住登录</span>
          <button type="button" onClick={() => setRegister((value) => !value)}>
            {register ? "返回登录" : "开户注册"}
          </button>
        </div>

        <button type="button" className="mobile-app-primary mobile-auth-submit" onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? "处理中" : register ? "注册并登录 →" : "登录进入工作台 →"}
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
  const [holdingEditor, setHoldingEditor] = useState<HoldingEditorState | null>(null)
  const [aiOpen, setAiOpen] = useState(false)
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)
  const [strategyFilter, setStrategyFilter] = useState<MobileStrategyTabKey>("first_board")
  const [playbook, setPlaybook] = useState<LowBuyScreenerResult | null>(null)
  const [playbookCache, setPlaybookCache] = useState<Partial<Record<MobileStrategyTabKey, LowBuyScreenerResult>>>({})
  const [playbookLoading, setPlaybookLoading] = useState(false)
  const [playbookError, setPlaybookError] = useState("")
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
  const [signalToastVisible, setSignalToastVisible] = useState(false)
  const lastSignalToastSignature = useRef("")
  useNativeRuntime(() => {
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

  const holdingRows = useMemo<MobileHoldingRowData[]>(() => {
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
          signal: liveCard?.signal ?? null,
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

  const activeHoldingSignalSymbols = useMemo(() => {
    return new Set(
      holdingRows
        .filter((row) =>
          isHoldingTSignalActive({
            symbol: row.record.symbol,
            action: row.signal?.action ?? "hold",
            lastPrice: row.quote?.last_price,
            entryPrice: row.signal?.entry_price,
            exitPrice: row.signal?.exit_price
          })
        )
        .map((row) => row.record.symbol)
    )
  }, [holdingRows])

  const holdingSignalSignature = useMemo(
    () =>
      buildHoldingSignalSignature(
        holdingRows.map((row) => ({
          symbol: row.record.symbol,
          action: row.signal?.action ?? "hold",
          lastPrice: row.quote?.last_price,
          entryPrice: row.signal?.entry_price,
          exitPrice: row.signal?.exit_price
        }))
      ),
    [holdingRows]
  )

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
  const playbookItems = useMemo(
    () => uniqueLowBuyCandidates([...(playbook?.confirmed_candidates ?? []), ...(playbook?.candidates ?? [])]),
    [playbook]
  )
  const playbookGroups = splitPriorityItems(playbookItems)
  const executableCount = (home?.summary.positive_t_count ?? 0) + (home?.summary.negative_t_count ?? 0)
  const monitorQualityScore = averageScore((home?.items ?? []).map((item) => item.signal.signal_score))

  const monitorMetrics = [
    {
      label: "持仓自选",
      value: String(home?.summary.total ?? 0)
    },
    {
      label: "可执行",
      value: String(executableCount),
      tone: "positive" as const
    },
    {
      label: "高风险",
      value: String(home?.summary.high_risk_count ?? 0),
      tone: "warning" as const
    },
    {
      label: "质量分",
      value: monitorQualityScore
    }
  ]

  const holdingsMetrics = [
    {
      label: "持仓股",
      value: String(holdingsSummary.count)
    },
    {
      label: "浮动盈亏",
      value: formatAmountCompact(holdingsSummary.totalFloatingPnL),
      tone: holdingsSummary.totalFloatingPnL >= 0 ? ("positive" as const) : ("negative" as const)
    },
    {
      label: "总市值",
      value: formatAmountCompact(holdingsSummary.totalMarketValue)
    },
    {
      label: "可用股",
      value: String(holdingRows.reduce((sum, row) => sum + row.record.available_position, 0))
    }
  ]

  const lowBuyMetrics = [
    {
      label: "立即",
      value: `${playbookGroups.buyNow.length}↑`,
      tone: "positive" as const
    },
    {
      label: "观察",
      value: String(playbookGroups.nearEntry.length),
      tone: "warning" as const
    },
    {
      label: "跟踪",
      value: String(playbookGroups.watch.length)
    },
    {
      label: "深筛",
      value: String(playbook?.scanned_count ?? "--"),
      tone: "positive" as const
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

  function openBoughtEditor(item: MobileLowBuyCardItem) {
    setHoldingEditor({
      mode: watchlistMap.has(item.symbol) ? "edit" : "buy",
      seed: createSeedFromLowBuyItem(item, watchlistMap.get(item.symbol))
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

  async function handleRemoveHolding(item: WatchlistItem) {
    const success = await removeWatchItem(item.symbol)
    if (success) {
      setHoldingEditor(null)
    }
  }

  function handleSwitchTab(nextTab: MobileTab) {
    setHoldingEditor(null)
    setDetail(null)
    setAccountMenuOpen(false)
    setSignalToastVisible(false)
    setActiveTab(nextTab)
    if (nextTab !== "paper") {
      setPreviewTab("home")
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

  async function loadMobilePlaybook(strategy: MobileStrategyTabKey = strategyFilter, force = false) {
    const cached = playbookCache[strategy]
    if (cached && !force) {
      setPlaybook(cached)
      return
    }
    try {
      setPlaybookLoading(true)
      setPlaybookError("")
      const result = await api.getLowBuyCandidates(strategy, 18, 480, false, "full")
      setPlaybook(result)
      setPlaybookCache((current) => ({ ...current, [strategy]: result }))
    } catch (err) {
      setPlaybookError(err instanceof Error ? err.message : "选股宝典加载失败")
    } finally {
      setPlaybookLoading(false)
    }
  }

  function handleStrategyChange(nextStrategy: MobileStrategyTabKey) {
    setStrategyFilter(nextStrategy)
  }

  useEffect(() => {
    if (authUser && activeTab === "paper" && !paperAccount && !paperLoading) {
      void loadPaper()
    }
  }, [activeTab, authUser, paperAccount, paperLoading])

  useEffect(() => {
    if (!authUser || activeTab !== "low_buy") {
      return
    }
    void loadMobilePlaybook(strategyFilter)
  }, [activeTab, authUser, strategyFilter])

  useEffect(() => {
    if (activeTab !== "holdings") {
      return
    }
    if (!holdingSignalSignature) {
      lastSignalToastSignature.current = ""
      setSignalToastVisible(false)
      return
    }
    if (lastSignalToastSignature.current === holdingSignalSignature) {
      return
    }
    lastSignalToastSignature.current = holdingSignalSignature
    setSignalToastVisible(true)
    const timeout = window.setTimeout(() => setSignalToastVisible(false), 3000)
    return () => window.clearTimeout(timeout)
  }, [activeTab, holdingSignalSignature])

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
          <h1>{activeTab === "home" ? "实时监控" : activeTab === "holdings" ? "持仓" : activeTab === "low_buy" ? "选股宝典" : "模拟交易"}</h1>
        </div>
        <div className="mobile-app-topbar-meta">
          {activeTab === "home" ? (
            <>
              <button type="button" className="mobile-app-icon-button" onClick={() => void refreshActiveTab()} aria-label="刷新">
                <Icon name="refresh" />
              </button>
              <span className="mobile-app-time">{pulseTime}</span>
            </>
          ) : activeTab === "holdings" ? (
            <>
              <button type="button" className="mobile-app-icon-button" onClick={() => void refreshActiveTab()} aria-label="刷新">
                <Icon name="refresh" />
              </button>
            </>
          ) : activeTab === "paper" ? (
            <>
              <button type="button" className="mobile-app-icon-button" onClick={() => void loadPaper()} aria-label="刷新">
                <Icon name="refresh" />
              </button>
            </>
          ) : (
            <>
              <button type="button" className="mobile-app-icon-button" onClick={() => void loadMobilePlaybook(strategyFilter, true)} aria-label="刷新">
                <Icon name="refresh" />
              </button>
            </>
          )}
          <AccountMenu
            user={authUser}
            open={accountMenuOpen}
            onToggle={() => setAccountMenuOpen((value) => !value)}
            onLogout={() => void handleLogout()}
          />
        </div>
      </header>

      {signalToastVisible ? <div className="mobile-app-signal-toast">已发现信号</div> : null}
      {message ? <div className="mobile-app-banner">{message}</div> : null}
      {error ? <div className="mobile-app-error">{error}</div> : null}
      {activeTab === "low_buy" && playbookError ? <div className="mobile-app-error">{playbookError}</div> : null}
      {activeTab === "paper" && paperMessage ? <div className="mobile-app-banner">{paperMessage}</div> : null}
      {activeTab === "paper" && paperError ? <div className="mobile-app-error">{paperError}</div> : null}

      <main className="mobile-app-body">
        {activeTab === "home" ? (
          <>
            <MobileMetricRow items={monitorMetrics} />
            <MobileMarketPills board={priorityBoard} />

            <MobileSectionTitle
              title="全策略优先级榜"
              hint={`按综合分排序 · ${priorityPulseTime} 刷新`}
              action={
                <button type="button" className="mobile-design-pill tone-gold" onClick={() => handleSwitchTab("low_buy")}>
                  去选股宝典
                </button>
              }
            />
            <section className="mobile-design-priority-scroll">
              {priorityBoardItems.slice(0, 5).map((item, index) => (
                <MobilePriorityStockCard
                  key={item.symbol}
                  item={item}
                  highlight={index === 0}
                  inWatchlist={watchlistMap.has(item.symbol)}
                  onOpen={openCandidate}
                />
              ))}
              {!loading && !priorityBoardItems.length ? (
                <div className="mobile-app-empty">当前没有榜单数据</div>
              ) : null}
            </section>

          </>
        ) : activeTab === "holdings" ? (
          <>
            <MobileMetricRow items={holdingsMetrics} />

            <MobileSectionTitle
              title={`持仓 (${holdingRows.length})`}
              hint="编辑成本价、持仓数、可用数"
              action={
                <button type="button" className="mobile-design-pill tone-gold" onClick={openCreateHolding}>
                  新增持仓
                </button>
              }
            />
            <section className="mobile-design-list">
              {holdingRows.map((row) => (
                <MobileHoldingStockCard
                  key={row.record.symbol}
                  row={row}
                  signalActive={activeHoldingSignalSymbols.has(row.record.symbol)}
                  onEdit={openEditHolding}
                  onRemove={handleRemoveHolding}
                />
              ))}
              {!loading && !holdingRows.length ? (
                <div className="mobile-app-empty">暂无持仓，点击右上角添加</div>
              ) : null}
            </section>
          </>
        ) : activeTab === "low_buy" ? (
          <>
            <MobileStrategyTabs active={strategyFilter} onChange={handleStrategyChange} />
            <MobileMetricRow items={lowBuyMetrics} />
            <MobileFocusCard item={playbookItems[0]} />

            <MobileSectionTitle
              title="确定买入"
              hint="优先执行"
              action={
                <button type="button" className="mobile-design-pill tone-gold" onClick={() => setAiOpen(true)}>
                  解读榜单
                </button>
              }
            />
            <section className="mobile-design-list">
              {playbookGroups.buyNow.slice(0, 4).map((item, index) => (
                <MobilePriorityStockCard
                  key={item.symbol}
                  item={item}
                  highlight={index === 0}
                  inWatchlist={watchlistMap.has(item.symbol)}
                  onOpen={(symbol) => void openCandidate(symbol, strategyFilter)}
                  onBought={openBoughtEditor}
                />
              ))}
              {!loading && !playbookLoading && !playbookGroups.buyNow.length ? (
                <div className="mobile-app-empty">当前策略暂无确定买入</div>
              ) : null}
            </section>

            <MobileSectionTitle title="接近买点" hint="等待确认" />
            <section className="mobile-design-list">
              {playbookGroups.nearEntry.slice(0, 4).map((item) => (
                <MobilePriorityStockCard
                  key={item.symbol}
                  item={item}
                  inWatchlist={watchlistMap.has(item.symbol)}
                  onOpen={(symbol) => void openCandidate(symbol, strategyFilter)}
                  onBought={openBoughtEditor}
                />
              ))}
              {!loading && !playbookLoading && !playbookGroups.nearEntry.length ? (
                <div className="mobile-app-empty">当前策略暂无接近买点</div>
              ) : null}
            </section>

            <MobileSectionTitle title="继续观察" hint="不急执行" />
            <section className="mobile-design-list">
              {playbookGroups.watch.slice(0, 4).map((item) => (
                <MobilePriorityStockCard
                  key={item.symbol}
                  item={item}
                  inWatchlist={watchlistMap.has(item.symbol)}
                  onOpen={(symbol) => void openCandidate(symbol, strategyFilter)}
                  onBought={openBoughtEditor}
                />
              ))}
              {!loading && !playbookLoading && !playbookGroups.watch.length ? (
                <div className="mobile-app-empty">当前策略暂无观察票</div>
              ) : null}
            </section>
          </>
        ) : (
          <PaperTradingPanel
            account={paperAccount}
            positions={paperPositions}
            orders={paperOrders}
            trades={paperTrades}
            performance={paperPerformance}
            strategyPerformance={paperStrategyPerformance}
            marketPerformance={paperMarketPerformance}
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
          className={activeTab === "holdings" ? "active" : ""}
          onClick={() => handleSwitchTab("holdings")}
        >
          <span>持仓</span>
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
          <span>模拟交易</span>
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

function AccountMenu({
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
