import { createQuery } from "@tanstack/solid-query";
import { For, Show, createEffect, createMemo, createSignal, onCleanup } from "solid-js";
import { getAdminApiToken } from "../../shared/api/auth";
import { requestOperation } from "../../shared/api/client";
import { queryKeys } from "../../shared/api/queryKeys";
import type { FactorWeightsResponse, QuantParametersResponse, SectorExclusionsResponse, SettingsResponse, SettingsWorkspaceResponse } from "../../shared/api/types";
import { useAuth } from "../auth/authModel";
import { readArray, readRecord, text } from "../shared/dataAccess";
import { PageScaffold } from "../shared/PageScaffold";
import { CardFooter, CommandCard, Icon, ModelBox, ScoreBadge, SelectField, SmallBadge, TextField, type SettingsAccent } from "./SettingsPrimitives";
import { factorRows, sectorRows } from "./settingsModel";
import "./settings-slice.css";

type ToastKind = "success" | "error" | "info";
type ToastItem = { id: number; message: string; type: ToastKind };
type StopLossTab = "basic" | "move" | "wash" | "exit";
type FactorView = { name: string; weight: number; accent: SettingsAccent };
type FieldDef = { key: string; label: string };

export function SettingsPage() {
  const auth = useAuth();
  const [isDarkMode, setIsDarkMode] = createSignal(false);
  const [notifications, setNotifications] = createSignal<ToastItem[]>([]);
  const [globalAdminToken, setGlobalAdminToken] = createSignal("");
  const [isTokenValid, setIsTokenValid] = createSignal(false);
  const [mfaEnabled, setMfaEnabled] = createSignal(false);
  const [verificationCode, setVerificationCode] = createSignal(["", "", "", "", "", ""]);
  const [redLuckIntensity, setRedLuckIntensity] = createSignal<"standard" | "minimalist" | "off">("standard");
  const [stopLossTab, setStopLossTab] = createSignal<StopLossTab>("basic");
  const [sectorSearch, setSectorSearch] = createSignal("");
  const [excludedSectors, setExcludedSectors] = createSignal(DEFAULT_EXCLUDED_SECTORS);
  const [sectorHydrated, setSectorHydrated] = createSignal(false);
  const [isLoadingFactors, setIsLoadingFactors] = createSignal(false);
  const [llmShowKey, setLlmShowKey] = createSignal(false);
  const [riskParams, setRiskParams] = createSignal({
    singleMaxLoss: "2.0",
    dailyMaxLoss: "5.0",
    consecutiveLossLimit: "3",
    minProfit: "1.5",
  });
  const [stopProfitLoss, setStopProfitLoss] = createSignal({
    hardStop: "6.0",
    firstProfitLine: "10.0",
    firstProfitRatio: "50%",
    profitProtectTrigger: "8.0",
    protectReduceRatio: "30%",
    moveProfitStart: "12.0",
    moveProfitRetracement: "2.5",
    moveProfitSellRatio: "40%",
    normalProfitLine: "15.0",
    normalProfitRatio: "60%",
    strongProfitLine: "25.0",
    strongProfitRatio: "100%",
    washToleranceProfit: "3.0",
    washMaxFloatingLoss: "-4.5",
    washVolShrinkLimit: "0.4",
    noVolJumpProfitLine: "18.0",
    noVolThreshold: "0.5",
    noVolProfitRatio: "30%",
    jumpRetraceProtect: "50%",
    minNetProfitThreshold: "1.0",
    washAddFunds: "20%",
    maxPositionLimit: "40%",
    gridExpectedRebound: "2.5",
    noTurnStrongDays: "5",
    timeExitMinProfit: "0.5",
  });
  const [etfParams, setEtfParams] = createSignal({
    enabled: true,
    maxOrdersPerRound: "5",
    singleAvailableFunds: "15%",
    minConfidence: "85%",
    minExpectedSpread: "0.8",
    stopProfitLine: "2.5",
    stopLossLine: "1.5",
  });
  const [llmConfig, setLlmConfig] = createSignal({
    provider: "OpenAI",
    modelName: "gpt-4o-mini",
    baseUrl: "https://api.openai.com/v1",
    apiKey: "••••••••••••••••••••••••",
  });
  const [fallbackFactors, setFallbackFactors] = createSignal<FactorView[]>([
    { name: "基本面因子", weight: 35, accent: "blue" },
    { name: "动量与技术面因子", weight: 25, accent: "emerald" },
    { name: "大模型情感因子", weight: 20, accent: "indigo" },
  ]);
  const [mlParams, setMlParams] = createSignal({
    kFold: "5",
    minSamples: "2000",
    xgBoostTrees: "150",
    xgBoostDepth: "6",
    xgBoostLr: "0.05",
    lightGbmTrees: "200",
    lightGbmDepth: "7",
    lightGbmLr: "0.03",
  });
  const toastTimers: number[] = [];
  let toastSerial = 0;

  const workspaceQuery = createQuery(() => ({
    queryKey: queryKeys.settingsWorkspace,
    queryFn: ({ signal }) => requestOperation<SettingsWorkspaceResponse>("settingsWorkspace", {}, { signal }),
    retry: false,
  }));
  const canUseDirectAdminEndpoints = createMemo(() => auth.isAdmin() && Boolean(getAdminApiToken()));
  const settingsQuery = createQuery(() => ({
    queryKey: queryKeys.settings,
    queryFn: ({ signal }) => requestOperation<SettingsResponse>("settings", {}, { signal }),
    retry: false,
    enabled: canUseDirectAdminEndpoints(),
  }));
  const sectorQuery = createQuery(() => ({
    queryKey: queryKeys.sectorExclusions,
    queryFn: ({ signal }) => requestOperation<SectorExclusionsResponse>("sectorExclusions", {}, { signal }),
    retry: false,
    enabled: canUseDirectAdminEndpoints(),
  }));
  const factorQuery = createQuery(() => ({
    queryKey: queryKeys.factorWeights,
    queryFn: ({ signal }) => requestOperation<FactorWeightsResponse>("factorWeights", {}, { signal }),
    retry: false,
    enabled: canUseDirectAdminEndpoints(),
  }));
  const quantQuery = createQuery(() => ({
    queryKey: queryKeys.quantParameters,
    queryFn: ({ signal }) => requestOperation<QuantParametersResponse>("quantParameters", {}, { signal }),
    retry: false,
    enabled: canUseDirectAdminEndpoints(),
  }));
  const workspaceRoot = createMemo(() => readRecord(workspaceQuery.data));
  const settingsRoot = createMemo(() => {
    const direct = readRecord(settingsQuery.data);
    return Object.keys(direct).length ? direct : readRecord(workspaceRoot().settings);
  });
  const sectorRoot = createMemo(() => sectorQuery.data ?? workspaceRoot().sector_exclusions);
  const factorRoot = createMemo(() => factorQuery.data ?? workspaceRoot().factor_weights);

  createEffect(() => {
    const user = auth.user();
    if (user) setMfaEnabled(Boolean(user.mfa_totp_enabled));
  });

  createEffect(() => {
    if (sectorHydrated()) return;
    const rows = sectorRows(sectorRoot());
    if (!rows.length) return;
    const nextExcluded = rows
      .filter((row) => row.excluded === true || text(row.excluded) === "true")
      .map((row) => text(row.sector, ""))
      .filter(Boolean);
    if (nextExcluded.length) setExcludedSectors(nextExcluded);
    setSectorHydrated(true);
  });

  onCleanup(() => {
    toastTimers.forEach((timer) => window.clearTimeout(timer));
  });

  const sectorNames = createMemo(() => {
    const apiSectors = sectorRows(sectorRoot()).map((row) => text(row.sector, "")).filter(Boolean);
    return Array.from(new Set([...INITIAL_SECTORS, ...apiSectors]));
  });
  const filteredSectors = createMemo(() => {
    const keyword = sectorSearch().trim().toLowerCase();
    if (!keyword) return sectorNames();
    return sectorNames().filter((sector) => sector.toLowerCase().includes(keyword));
  });
  const apiFactors = createMemo<FactorView[]>(() => {
    const accents: SettingsAccent[] = ["blue", "emerald", "indigo", "amber", "rose"];
    return factorRows(factorRoot()).slice(0, 8).map((row, index) => ({
      name: text(row.name ?? row.key, `因子 ${index + 1}`),
      weight: numericWeight(row.weight),
      accent: accents[index % accents.length],
    })).filter((item) => item.name !== "--");
  });
  const visibleFactors = createMemo(() => (apiFactors().length ? apiFactors() : fallbackFactors()));
  const activeStopFields = createMemo(() => STOP_LOSS_GROUPS[stopLossTab()]);
  const quantVersions = createMemo(() => readArray(readRecord(quantQuery.data).items).slice(0, 3).map((item) => {
    const row = readRecord(item);
    return {
      name: text(row.name ?? row.version, "参数版本"),
      status: text(row.status, "ready"),
      count: String(Object.keys(readRecord(row.params)).length || text(row.param_count, "0")),
    };
  }));
  const liveSummary = createMemo(() => ({
    dataSource: text(settingsRoot().data_source, "--"),
    db: text(settingsRoot().database_url_configured, "--"),
    llm: text(settingsRoot().llm_provider, llmConfig().provider),
    model: text(settingsRoot().llm_model, llmConfig().modelName),
  }));

  const triggerToast = (message: string, type: ToastKind = "success") => {
    const id = Date.now() + toastSerial;
    toastSerial += 1;
    setNotifications((prev) => [...prev, { id, message, type }].slice(-4));
    const timer = window.setTimeout(() => {
      setNotifications((prev) => prev.filter((item) => item.id !== id));
    }, 3000);
    toastTimers.push(timer);
  };

  const handleVerifyToken = () => {
    const token = globalAdminToken().trim();
    if (token === "ADMIN_TOKEN") {
      setIsTokenValid(true);
      triggerToast("管理员权限校验通过，本页本地编辑已解锁。");
      return;
    }
    setIsTokenValid(false);
    triggerToast(token ? "令牌不匹配，请使用测试令牌 ADMIN_TOKEN。" : "请输入管理令牌。", "error");
  };

  const handleSaveModule = (moduleName: string) => {
    if (!isTokenValid()) {
      triggerToast(`[${moduleName}] 需要先校验管理令牌。`, "error");
      return;
    }
    triggerToast(`[${moduleName}] 已记录本地配置意图，正式保存待复验后开启。`);
  };

  const handleCodeChange = (index: number, value: string) => {
    if (!/^\d?$/.test(value)) return;
    setVerificationCode((prev) => {
      const next = [...prev];
      next[index] = value.slice(-1);
      return next;
    });
    if (value && index < 5) {
      window.setTimeout(() => document.getElementById(`settings-mfa-code-${index + 1}`)?.focus(), 0);
    }
  };

  const handleMfaEnable = () => {
    if (verificationCode().join("").length !== 6) {
      triggerToast("请输入完整的 6 位动态验证码。", "error");
      return;
    }
    setMfaEnabled(true);
    triggerToast("2FA 二次验证已在本地激活。");
  };

  const toggleSector = (sector: string) => {
    setExcludedSectors((prev) => (prev.includes(sector) ? prev.filter((item) => item !== sector) : [...prev, sector]));
  };

  const reloadFactors = () => {
    if (!isTokenValid()) {
      triggerToast("请先在顶部校验管理令牌。", "error");
      return;
    }
    setIsLoadingFactors(true);
    void factorQuery.refetch().finally(() => {
      setFallbackFactors([
        { name: "基本面因子", weight: 35, accent: "blue" },
        { name: "动量与技术面因子", weight: 25, accent: "emerald" },
        { name: "大模型情感因子", weight: 20, accent: "indigo" },
        { name: "市场波动率因子", weight: 12, accent: "amber" },
        { name: "资金流向因子", weight: 8, accent: "rose" },
      ]);
      setIsLoadingFactors(false);
      triggerToast("因子权重已重载。");
    });
  };

  const refreshAll = () => {
    void Promise.allSettled([settingsQuery.refetch(), sectorQuery.refetch(), factorQuery.refetch(), quantQuery.refetch()]).then(() => {
      triggerToast("配置数据已刷新。", "info");
    });
  };

  return (
    <PageScaffold page="settings" class={`settings-command-page${isDarkMode() ? " settings-command-page--dark" : ""}`}>
      <section class="settings-command tq-page__full" aria-label="系统设置量化综合面板">
        <header class="settings-command-header">
          <div class="settings-command-brand">
            <span class="settings-command-brand__mark">Q</span>
            <div>
              <h1>QUANT COMMAND 极致量化综合面板</h1>
              <p>账户安全 · 交易偏好 · 模型因子 · 风控过滤 · ML 参数</p>
            </div>
          </div>

          <div class="settings-command-token">
            <Icon name="key" />
            <strong>管理员令牌锁</strong>
            <input
              type="password"
              placeholder="管理令牌(测试用: ADMIN_TOKEN)"
              value={globalAdminToken()}
              onInput={(event) => setGlobalAdminToken(event.currentTarget.value)}
            />
            <button type="button" class="settings-command-button settings-command-button--primary" onClick={handleVerifyToken}>
              {isTokenValid() ? <Icon name="unlock" /> : <Icon name="lock" />}
              解锁
            </button>
            <Show when={isTokenValid()}>
              <button
                type="button"
                class="settings-command-icon-button settings-command-icon-button--danger"
                title="清除授权"
                onClick={() => {
                  setIsTokenValid(false);
                  setGlobalAdminToken("");
                  triggerToast("特权已注销。", "info");
                }}
              >
                <Icon name="x" />
              </button>
            </Show>
          </div>

          <div class="settings-command-tools">
            <button type="button" class="settings-command-icon-button" title="刷新配置" onClick={refreshAll}>
              <Icon name="refresh" />
            </button>
            <button type="button" class="settings-command-icon-button" title="切换主题" onClick={() => setIsDarkMode((value) => !value)}>
              <Icon name={isDarkMode() ? "sun" : "moon"} />
            </button>
            <span class={`settings-command-status${isTokenValid() ? " settings-command-status--ok" : ""}`}>
              <i />
              {isTokenValid() ? "ADMIN AUTHED" : "READ ONLY"}
            </span>
            <button type="button" class="settings-command-button settings-command-button--primary" onClick={() => handleSaveModule("全局配置")}>
              <Icon name="save" />
              记录全部意图
            </button>
          </div>
        </header>

        <main class="settings-command-grid">
          <div class="settings-command-column">
            <CommandCard title="账户安全与 2FA 动态认证" index="1" icon="shield" accent="indigo" action={<ScoreBadge enabled={mfaEnabled()} />}>
              <Show
                when={!mfaEnabled()}
                fallback={
                  <div class="settings-command-mfa-done">
                    <Icon name="check" />
                    <strong>2FA 双因素强认证保护中</strong>
                    <button
                      type="button"
                      onClick={() => {
                        setMfaEnabled(false);
                        setVerificationCode(["", "", "", "", "", ""]);
                      }}
                    >
                      停用二次验证
                    </button>
                  </div>
                }
              >
                <div class="settings-command-note settings-command-note--amber">
                  <strong>安全提示：</strong>验证码只用于管理员配置与敏感入口校验，不参与量化模型和交易策略。
                </div>
                <div class="settings-command-steps">
                  <span>1.下认证器</span>
                  <span>2.存加密钥</span>
                  <span>3.填校验码</span>
                  <span>4.启用成功</span>
                </div>
                <div class="settings-command-secret">
                  <span class="settings-command-qr"><Icon name="qr" /></span>
                  <div>
                    <span>扫码备份密钥</span>
                    <input readonly value="MFA_SECRET_AUTH_KEY_QNT_2026" />
                  </div>
                </div>
                <div class="settings-command-code-row">
                  <div class="settings-command-code-boxes">
                    <For each={verificationCode()}>
                      {(digit, index) => (
                        <input
                          id={`settings-mfa-code-${index()}`}
                          inputmode="numeric"
                          maxlength="1"
                          value={digit}
                          onInput={(event) => handleCodeChange(index(), event.currentTarget.value)}
                        />
                      )}
                    </For>
                  </div>
                  <button type="button" class="settings-command-button settings-command-button--primary" onClick={handleMfaEnable}>
                    立即校验
                  </button>
                </div>
              </Show>
            </CommandCard>

            <CommandCard title="大模型底层底座" index="2" icon="cpu" accent="indigo" action={<SmallBadge tone="ok">已加密保存</SmallBadge>}>
              <div class="settings-command-form-grid settings-command-form-grid--two">
                <SelectField
                  label="大模型供应商"
                  value={llmConfig().provider}
                  options={["OpenAI", "Anthropic", "DeepSeek", "Google Gemini"]}
                  onChange={(value) => setLlmConfig((prev) => ({ ...prev, provider: value }))}
                />
                <TextField label="大模型名称" value={llmConfig().modelName} onInput={(value) => setLlmConfig((prev) => ({ ...prev, modelName: value }))} />
              </div>
              <TextField label="API Endpoint Base URL" value={llmConfig().baseUrl} onInput={(value) => setLlmConfig((prev) => ({ ...prev, baseUrl: value }))} />
              <div class="settings-command-secret-input">
                <TextField
                  label="API Authentication Key"
                  type={llmShowKey() ? "text" : "password"}
                  value={llmConfig().apiKey}
                  onInput={(value) => setLlmConfig((prev) => ({ ...prev, apiKey: value }))}
                />
                <button type="button" class="settings-command-icon-button" title="显示/隐藏密钥" onClick={() => setLlmShowKey((value) => !value)}>
                  <Icon name={llmShowKey() ? "eyeOff" : "eye"} />
                </button>
              </div>
              <div class="settings-command-live-strip">
                <span>运行 Provider: {liveSummary().llm}</span>
                <span>Model: {liveSummary().model}</span>
              </div>
            </CommandCard>

            <CommandCard
              title="因子权重配置"
              index="3"
              icon="sliders"
              accent="emerald"
              class="settings-command-card--stretch"
              action={
                <button type="button" class={`settings-command-mini-button${isLoadingFactors() ? " settings-command-mini-button--loading" : ""}`} onClick={reloadFactors}>
                  <Icon name="refresh" />
                  重载拉取
                </button>
              }
            >
              <div class="settings-command-factor-list">
                <For each={visibleFactors()}>
                  {(factor) => (
                    <div class="settings-command-factor">
                      <div>
                        <span>{factor.name}</span>
                        <strong>{factor.weight}%</strong>
                      </div>
                      <i class={`settings-command-factor__bar settings-command-factor__bar--${factor.accent}`} style={{ width: `${clampPercent(factor.weight)}%` }} />
                    </div>
                  )}
                </For>
              </div>
              <div class="settings-command-ritual">
                <div>
                  <strong>红运仪式感强度</strong>
                  <span>仅视觉层，策略零干扰</span>
                </div>
                <div class="settings-command-segment">
                  <For each={RED_LUCK_MODES}>
                    {(mode) => (
                      <button
                        type="button"
                        class={redLuckIntensity() === mode.key ? "settings-command-segment__item settings-command-segment__item--active" : "settings-command-segment__item"}
                        onClick={() => {
                          setRedLuckIntensity(mode.key);
                          triggerToast(`已应用仪式感：${mode.label}`, "info");
                        }}
                      >
                        {mode.label}
                      </button>
                    )}
                  </For>
                </div>
              </div>
            </CommandCard>
          </div>

          <div class="settings-command-column">
            <CommandCard title="交易风控通道 & ETF T+0 参数" index="4" icon="activity" accent="emerald">
              <div class="settings-command-form-grid settings-command-form-grid--four">
                <TextField label="单笔亏损(%)" value={riskParams().singleMaxLoss} align="center" onInput={(value) => setRiskParams((prev) => ({ ...prev, singleMaxLoss: value }))} />
                <TextField label="日内亏损(%)" value={riskParams().dailyMaxLoss} align="center" onInput={(value) => setRiskParams((prev) => ({ ...prev, dailyMaxLoss: value }))} />
                <TextField label="连亏暂停(次)" value={riskParams().consecutiveLossLimit} align="center" onInput={(value) => setRiskParams((prev) => ({ ...prev, consecutiveLossLimit: value }))} />
                <TextField label="最小收益(%)" value={riskParams().minProfit} align="center" onInput={(value) => setRiskParams((prev) => ({ ...prev, minProfit: value }))} />
              </div>
              <div class="settings-command-subpanel">
                <div class="settings-command-subpanel__head">
                  <strong>行业 ETF T+0 自动交易系统</strong>
                  <button
                    type="button"
                    class={`settings-command-switch${etfParams().enabled ? " settings-command-switch--on" : ""}`}
                    onClick={() => setEtfParams((prev) => ({ ...prev, enabled: !prev.enabled }))}
                  >
                    <span />
                  </button>
                </div>
                <div class="settings-command-form-grid settings-command-form-grid--three">
                  <TextField label="单轮最多委托" value={etfParams().maxOrdersPerRound} onInput={(value) => setEtfParams((prev) => ({ ...prev, maxOrdersPerRound: value }))} />
                  <TextField label="单笔资金比" value={etfParams().singleAvailableFunds} onInput={(value) => setEtfParams((prev) => ({ ...prev, singleAvailableFunds: value }))} />
                  <TextField label="最低置信度" value={etfParams().minConfidence} onInput={(value) => setEtfParams((prev) => ({ ...prev, minConfidence: value }))} />
                </div>
              </div>
              <CardFooter text="顶部验证管理令牌后，本页先记录本地配置意图。" onSave={() => handleSaveModule("风控及 ETF 通道参数")} />
            </CommandCard>

            <CommandCard title={`板块行业排除过滤机制 (${sectorNames().length}个)`} index="5" icon="layers" accent="indigo" class="settings-command-card--sector" action={<SmallBadge tone="danger">已屏蔽 {excludedSectors().length}</SmallBadge>}>
              <div class="settings-command-search">
                <Icon name="search" />
                <input
                  type="text"
                  placeholder="搜索不想参与过滤的板块..."
                  value={sectorSearch()}
                  onInput={(event) => setSectorSearch(event.currentTarget.value)}
                />
                <Show when={sectorSearch()}>
                  <button type="button" onClick={() => setSectorSearch("")}>
                    <Icon name="x" />
                  </button>
                </Show>
              </div>
              <div class="settings-command-sector-list">
                <For each={filteredSectors()}>
                  {(sector) => {
                    const excluded = createMemo(() => excludedSectors().includes(sector));
                    return (
                      <button
                        type="button"
                        class={`settings-command-sector-chip${excluded() ? " settings-command-sector-chip--excluded" : ""}`}
                        onClick={() => toggleSector(sector)}
                      >
                        <Show when={excluded()}><Icon name="x" /></Show>
                        {sector}
                      </button>
                    );
                  }}
                </For>
              </div>
              <div class="settings-command-excluded-summary">
                <strong>已排除汇总: </strong>
                <span>{excludedSectors().join("、") || "暂无排除项"}</span>
              </div>
            </CommandCard>

            <div class="settings-command-link-card">
              <Icon name="database" />
              <div>
                <strong>数据中心交易标的池</strong>
                <span>股票 & ETF 范围由数据底座统一维护</span>
              </div>
              <button type="button" onClick={() => triggerToast("数据中心入口保持在左侧菜单。", "info")}>
                接入中心
                <Icon name="chevron" />
              </button>
            </div>
          </div>

          <div class="settings-command-column">
            <CommandCard title="模拟盘 24 维动态止盈止损参数" index="6" icon="trend" accent="rose">
              <div class="settings-command-tabs">
                <For each={STOP_LOSS_TABS}>
                  {(item) => (
                    <button type="button" class={stopLossTab() === item.key ? "settings-command-tabs__item settings-command-tabs__item--active" : "settings-command-tabs__item"} onClick={() => setStopLossTab(item.key)}>
                      {item.label}
                    </button>
                  )}
                </For>
              </div>
              <div class="settings-command-form-grid settings-command-form-grid--two settings-command-form-grid--boxed">
                <For each={activeStopFields()}>
                  {(field) => (
                    <TextField
                      label={field.label}
                      value={stopProfitLoss()[field.key as keyof ReturnType<typeof stopProfitLoss>]}
                      onInput={(value) => setStopProfitLoss((prev) => ({ ...prev, [field.key]: value }))}
                    />
                  )}
                </For>
              </div>
              <CardFooter text="24 维高级算法控制 · 仅本地编辑态" onSave={() => handleSaveModule("24维动态盈损参数")} />
            </CommandCard>

            <CommandCard title="ML 机器学习模型深度参数" index="7" icon="sliders" accent="amber" class="settings-command-card--stretch" action={<SmallBadge tone="warn">新训练生效</SmallBadge>}>
              <div class="settings-command-form-grid settings-command-form-grid--two">
                <TextField label="K-fold 交叉验证折数" type="number" value={mlParams().kFold} onInput={(value) => setMlParams((prev) => ({ ...prev, kFold: value }))} />
                <TextField label="最低模型训练样本量" type="number" value={mlParams().minSamples} onInput={(value) => setMlParams((prev) => ({ ...prev, minSamples: value }))} />
              </div>
              <div class="settings-command-model-grid">
                <ModelBox
                  title="XGBoost 超参数"
                  accent="indigo"
                  fields={[
                    { label: "树数量", value: mlParams().xgBoostTrees, onInput: (value) => setMlParams((prev) => ({ ...prev, xgBoostTrees: value })) },
                    { label: "深度", value: mlParams().xgBoostDepth, onInput: (value) => setMlParams((prev) => ({ ...prev, xgBoostDepth: value })) },
                    { label: "学习率", value: mlParams().xgBoostLr, onInput: (value) => setMlParams((prev) => ({ ...prev, xgBoostLr: value })) },
                  ]}
                />
                <ModelBox
                  title="LightGBM 超参数"
                  accent="emerald"
                  fields={[
                    { label: "树数量", value: mlParams().lightGbmTrees, onInput: (value) => setMlParams((prev) => ({ ...prev, lightGbmTrees: value })) },
                    { label: "深度", value: mlParams().lightGbmDepth, onInput: (value) => setMlParams((prev) => ({ ...prev, lightGbmDepth: value })) },
                    { label: "学习率", value: mlParams().lightGbmLr, onInput: (value) => setMlParams((prev) => ({ ...prev, lightGbmLr: value })) },
                  ]}
                />
              </div>
              <div class="settings-command-quant-list">
                <For each={quantVersions()}>
                  {(item) => (
                    <span>
                      <strong>{item.name}</strong>
                      {item.status} · {item.count}项
                    </span>
                  )}
                </For>
                <Show when={!quantVersions().length}>
                  <span><strong>量化参数</strong>等待后端返回</span>
                </Show>
              </div>
              <CardFooter text="训练参数修改不影响历史模型。" onSave={() => handleSaveModule("ML 训练参数")} />
            </CommandCard>
          </div>
        </main>

        <footer class="settings-command-footer">
          <span>Quant Command v4.9.0 · 数据源 {liveSummary().dataSource} · DB {liveSummary().db}</span>
          <span>新前端设置页：本地交互态，不直接改变生产策略语义。</span>
        </footer>

        <div class="settings-command-toast-stack" aria-live="polite">
          <For each={notifications()}>
            {(item) => (
              <div class={`settings-command-toast settings-command-toast--${item.type}`}>
                <Icon name={item.type === "success" ? "check" : item.type === "error" ? "alert" : "info"} />
                <span>{item.message}</span>
              </div>
            )}
          </For>
        </div>
      </section>
    </PageScaffold>
  );
}

function numericWeight(value: unknown): number {
  const raw = Number(value);
  if (Number.isFinite(raw)) return Math.round(raw > 1 ? raw : raw * 100);
  return 0;
}

function clampPercent(value: number): number {
  return Math.max(4, Math.min(100, value));
}

const RED_LUCK_MODES: { key: "standard" | "minimalist" | "off"; label: string }[] = [
  { key: "standard", label: "标准" },
  { key: "minimalist", label: "克制" },
  { key: "off", label: "关闭" },
];

const STOP_LOSS_TABS: { key: StopLossTab; label: string }[] = [
  { key: "basic", label: "止盈止损" },
  { key: "move", label: "移动保护" },
  { key: "wash", label: "洗盘加仓" },
  { key: "exit", label: "退出反抽" },
];

const STOP_LOSS_GROUPS: Record<StopLossTab, FieldDef[]> = {
  basic: [
    { key: "hardStop", label: "硬止损线 (%)" },
    { key: "firstProfitLine", label: "第一止盈线 (%)" },
    { key: "firstProfitRatio", label: "第一止盈比例" },
    { key: "normalProfitLine", label: "常规止盈线 (%)" },
    { key: "normalProfitRatio", label: "常规止盈比例" },
    { key: "strongProfitLine", label: "强止盈线 (%)" },
  ],
  move: [
    { key: "profitProtectTrigger", label: "利润保护触发 (%)" },
    { key: "protectReduceRatio", label: "保护减仓比例" },
    { key: "moveProfitStart", label: "移动止盈启动 (%)" },
    { key: "moveProfitRetracement", label: "移动止盈回撤 (%)" },
    { key: "moveProfitSellRatio", label: "移动止盈卖出" },
    { key: "noVolJumpProfitLine", label: "无量冲高止盈线 (%)" },
  ],
  wash: [
    { key: "washToleranceProfit", label: "洗盘容忍收益 (%)" },
    { key: "washMaxFloatingLoss", label: "洗盘最大浮亏 (%)" },
    { key: "washVolShrinkLimit", label: "洗盘缩量上限" },
    { key: "washAddFunds", label: "洗盘加仓资金" },
    { key: "maxPositionLimit", label: "加仓后单票上限 (%)" },
    { key: "noVolThreshold", label: "无量判定阈值" },
  ],
  exit: [
    { key: "minNetProfitThreshold", label: "最低净收益门槛 (%)" },
    { key: "gridExpectedRebound", label: "做T预期反抽 (%)" },
    { key: "noTurnStrongDays", label: "未转强退出天数" },
    { key: "timeExitMinProfit", label: "时间退出最低收益 (%)" },
    { key: "noVolProfitRatio", label: "无量止盈比例" },
    { key: "jumpRetraceProtect", label: "冲高回落保护" },
  ],
};

const DEFAULT_EXCLUDED_SECTORS = [
  "专业连锁Ⅱ",
  "个护用品",
  "中药Ⅱ",
  "互联网电商",
  "休闲食品",
  "传媒",
  "体育Ⅱ",
  "保险",
  "保险Ⅱ",
  "养殖",
  "养殖业",
  "农商行Ⅱ",
  "房地产",
  "教育",
  "旅游酒店",
  "游戏",
  "白酒",
  "证券",
  "银行",
  "煤炭",
  "钢铁",
  "房地产开发",
  "房地产服务",
  "影视院线",
];

const INITIAL_SECTORS = [
  "IT服务Ⅱ",
  "一般零售",
  "专业工程",
  "专业服务",
  "专业连锁Ⅱ",
  "专用设备",
  "个护用品",
  "中药Ⅱ",
  "乘用车",
  "互联网电商",
  "人工智能",
  "休闲食品",
  "传媒",
  "体育Ⅱ",
  "保险",
  "保险Ⅱ",
  "储能",
  "元件",
  "光伏设备",
  "光学光电子",
  "其他家电Ⅱ",
  "其他电子Ⅱ",
  "其他电源设备Ⅱ",
  "养殖",
  "养殖业",
  "军工",
  "军工电子Ⅱ",
  "农业",
  "农业综合Ⅱ",
  "农产品加工",
  "农化制品",
  "农商行Ⅱ",
  "冶钢原料",
  "出版",
  "券商/证券",
  "动物保健Ⅱ",
  "包装印刷",
  "化妆品",
  "化学制品",
  "化学制药",
  "化学原料",
  "化学纤维",
  "化工",
  "医疗器械",
  "医疗服务",
  "医疗美容",
  "医药",
  "医药商业",
  "半导体",
  "半导体/芯片",
  "厨卫电器",
  "商用车",
  "国有大型银行Ⅱ",
  "国防军工",
  "地面兵装Ⅱ",
  "城商行Ⅱ",
  "基础建设",
  "塑料",
  "多元金融",
  "央企/中字头",
  "家居用品",
  "家电",
  "家电零部件Ⅱ",
  "宽基",
  "宽基/未识别",
  "小家电",
  "小金属",
  "工业金属",
  "工程咨询服务Ⅱ",
  "工程机械",
  "广告营销",
  "建筑工程",
  "影视院线",
  "成长风格",
  "房地产",
  "房地产开发",
  "房地产服务",
  "房屋建设Ⅱ",
  "摩托车及其他",
  "教育",
  "数字媒体",
  "文娱用品",
  "新能源",
  "新能源汽车",
  "旅游及景区",
  "旅游酒店",
  "旅游零售Ⅱ",
  "普钢",
  "有色金属",
  "服装家纺",
  "机器人",
  "林业Ⅱ",
  "橡胶",
  "水泥",
  "汽车服务",
  "汽车零部件",
  "油服工程",
  "油气开采Ⅱ",
  "消费",
  "消费电子",
  "渔业",
  "港口航运",
  "游戏",
  "游戏Ⅱ",
  "炼化及贸易",
  "焦炭Ⅱ",
  "煤炭",
  "煤炭开采",
  "照明设备Ⅱ",
  "燃气",
  "燃气Ⅱ",
  "物流",
  "特钢Ⅱ",
  "环保",
  "环保设备Ⅱ",
  "环境治理",
  "玻璃玻纤",
  "生物制品",
  "电力",
  "电力设备",
  "电子元件",
  "电子化学品Ⅱ",
  "电机Ⅱ",
  "电池",
  "电网设备",
  "电视广播Ⅱ",
  "白色家电",
  "白酒",
  "白酒Ⅱ",
  "种植业",
  "科创成长",
  "红利",
  "纺织制造",
  "纺织服装",
  "综合Ⅱ",
  "股份制银行Ⅱ",
  "能源金属",
  "自动化设备",
  "航天航空",
  "航天装备Ⅱ",
  "航海装备Ⅱ",
  "航空机场",
  "航空装备Ⅱ",
  "航运港口",
  "船舶制造",
  "装修建材",
  "装修装饰Ⅱ",
  "计算机设备",
  "证券",
  "证券Ⅱ",
  "调味发酵品Ⅱ",
  "贵金属",
  "贸易Ⅱ",
  "轨交设备Ⅱ",
  "软件开发",
  "软件服务",
  "通信服务",
  "通信设备",
  "通用设备",
  "造纸",
  "酒店餐饮",
  "金属新材料",
  "钢铁",
  "铁路公路",
  "银行",
  "银行Ⅱ",
  "非白酒",
  "非金属材料Ⅱ",
  "风电设备",
  "食品加工",
  "食品饮料",
  "饮料乳品",
  "饰品",
  "饲料",
  "黑色家电",
];
