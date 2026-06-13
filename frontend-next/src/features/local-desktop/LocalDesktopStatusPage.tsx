import { createQuery } from "@tanstack/solid-query";
import { For, Show, createMemo, createSignal, onMount } from "solid-js";
import { apiClient } from "../../shared/api/client";
import { getEffectiveApiBaseUrl, getRuntimeApiBaseUrl, setRuntimeApiBaseUrl } from "../../shared/api/runtimeBaseUrl";
import { queryKeys } from "../../shared/api/queryKeys";
import { Button } from "../../shared/ui/Button";
import { Icon } from "../../shared/ui/Icon";
import { PageScaffold } from "../shared/PageScaffold";
import { createLocalDesktopStatusModel } from "./localDesktopModel";
import { openDesktopPath, readDesktopConfig, writeDesktopConfig, type DesktopCommand } from "./tauriBridge";
import "./local-desktop.css";

export function LocalDesktopStatusPage() {
  const [apiBaseInput, setApiBaseInput] = createSignal(getRuntimeApiBaseUrl());
  const [commandMessage, setCommandMessage] = createSignal("");
  const [configSource, setConfigSource] = createSignal("浏览器本地存储");

  const statusQuery = createQuery(() => ({
    queryKey: queryKeys.localDesktopStatus(getRuntimeApiBaseUrl()),
    queryFn: ({ signal }) => apiClient.localDesktopStatus({ signal }),
    retry: false,
  }));
  const model = createMemo(() => createLocalDesktopStatusModel(statusQuery.data, statusQuery.error));
  const currentApiBase = createMemo(() => getEffectiveApiBaseUrl() || "相对路径");

  onMount(() => {
    void readDesktopConfig()
      .then((config) => {
        setConfigSource("Tauri 本地 JSON");
        if (config.apiBaseUrl) {
          setRuntimeApiBaseUrl(config.apiBaseUrl);
          setApiBaseInput(config.apiBaseUrl);
          void statusQuery.refetch();
        }
      })
      .catch(() => {
        setConfigSource("浏览器本地存储");
      });
  });

  const saveApiBase = async () => {
    const saved = setRuntimeApiBaseUrl(apiBaseInput());
    try {
      const config = await writeDesktopConfig(saved);
      setConfigSource("Tauri 本地 JSON");
      setApiBaseInput(config.apiBaseUrl);
      setRuntimeApiBaseUrl(config.apiBaseUrl);
      setCommandMessage(config.apiBaseUrl ? `已保存 API 地址：${config.apiBaseUrl}` : "已清除 API 地址，恢复默认请求路径。");
    } catch {
      setApiBaseInput(saved);
      setCommandMessage(saved ? `已保存 API 地址：${saved}` : "已清除 API 地址，恢复默认请求路径。");
    }
    void statusQuery.refetch();
  };

  const openPath = async (command: DesktopCommand) => {
    try {
      await openDesktopPath(command);
      setCommandMessage(command === "open_log_dir" ? "已请求打开日志目录。" : "已请求打开数据目录。");
    } catch (error) {
      setCommandMessage(error instanceof Error ? error.message : typeof error === "string" ? error : "目录打开失败。");
    }
  };

  return (
    <PageScaffold page="local-status" class="local-desktop-page">
      <section class="local-desktop-shell tq-page__full" aria-label="本机桌面应用状态">
        <header class="local-desktop-hero">
          <div>
            <div class="local-desktop-eyebrow">
              <Icon name="cpu" />
              <span>本机运行状态</span>
            </div>
            <h1>本地量化桌面端</h1>
            <p>只读检查后端、缓存、运行时和本机目录状态；页面不执行部署、清理、生产配置修改或交易动作。</p>
          </div>
          <div class={`local-desktop-status local-desktop-status--${model().overallStatus}`}>
            <span>{model().statusText}</span>
            <strong>{model().summary}</strong>
          </div>
        </header>

        <section class="local-desktop-grid local-desktop-grid--top">
          <article class="local-panel local-panel--wide">
            <div class="local-panel__header">
              <div>
                <h2>API 地址</h2>
                <p>当前：{currentApiBase()} · 配置来源：{configSource()}</p>
              </div>
              <Button variant="subtle" size="sm" icon={<Icon name="refresh" />} onClick={() => void statusQuery.refetch()}>
                重检
              </Button>
            </div>
            <div class="local-api-form">
              <label>
                <span>本机 API Base URL</span>
                <input
                  value={apiBaseInput()}
                  placeholder="http://127.0.0.1:8000"
                  onInput={(event) => setApiBaseInput(event.currentTarget.value)}
                />
              </label>
              <Button variant="primary" size="sm" icon={<Icon name="save" />} onClick={saveApiBase}>
                保存
              </Button>
            </div>
            <Show when={commandMessage()}>
              <p class="local-desktop-message">{commandMessage()}</p>
            </Show>
          </article>

          <article class="local-panel">
            <div class="local-panel__header">
              <div>
                <h2>版本</h2>
                <p>{model().app} · {model().environment}</p>
              </div>
              <span class="local-version">{model().version}</span>
            </div>
            <dl class="local-meta-list">
              <div>
                <dt>检查时间</dt>
                <dd>{model().generatedAt}</dd>
              </div>
              <div>
                <dt>刷新状态</dt>
                <dd>{statusQuery.isFetching ? "检查中" : "已完成"}</dd>
              </div>
            </dl>
          </article>
        </section>

        <section class="local-desktop-grid">
          <article class="local-panel local-panel--wide">
            <div class="local-panel__header">
              <div>
                <h2>服务组件</h2>
                <p>结果来自后端只读接口，桌面端不重算策略状态。</p>
              </div>
            </div>
            <div class="local-component-list">
              <For each={model().components}>
                {(component) => (
                  <div class={`local-component local-component--${component.status}`}>
                    <div>
                      <strong>{component.label}</strong>
                      <span>{component.message}</span>
                    </div>
                    <div>
                      <em>{component.latencyText}</em>
                      <b>{component.statusText}</b>
                    </div>
                  </div>
                )}
              </For>
            </div>
          </article>

          <article class="local-panel">
            <div class="local-panel__header">
              <div>
                <h2>目录入口</h2>
                <p>仅打开本机目录。</p>
              </div>
            </div>
            <div class="local-dir-actions">
              <Button variant="subtle" size="sm" icon={<Icon name="file" />} onClick={() => void openPath("open_log_dir")}>
                日志目录
              </Button>
              <Button variant="subtle" size="sm" icon={<Icon name="database" />} onClick={() => void openPath("open_data_dir")}>
                数据目录
              </Button>
            </div>
            <div class="local-dir-list">
              <For each={model().directories}>
                {(directory) => (
                  <div>
                    <span>{directory.label}</span>
                    <strong>{directory.exists ? "存在" : "缺失"}</strong>
                    <code>{directory.path}</code>
                  </div>
                )}
              </For>
            </div>
          </article>
        </section>

        <section class="local-panel tq-page__full">
          <div class="local-panel__header">
            <div>
              <h2>本机启动引导</h2>
              <p>仅展示本地命令；桌面端不会自动启动、停止或重启任何进程。</p>
            </div>
          </div>
          <div class="local-launch-grid">
            <For each={model().launchGuides}>
              {(guide) => (
                <div class="local-launch">
                  <div>
                    <strong>{guide.label}</strong>
                    <span>{guide.badgeText}</span>
                  </div>
                  <p>{guide.description}</p>
                  <code>{guide.command}</code>
                </div>
              )}
            </For>
          </div>
        </section>

        <section class="local-panel tq-page__full">
          <div class="local-panel__header">
            <div>
              <h2>安全边界</h2>
              <p>桌面端第一版仅开放本机检查和目录入口。</p>
            </div>
          </div>
          <div class="local-safety-grid">
            <For each={model().safety}>
              {(item) => (
                <div class={`local-safety local-safety--${item.allowed ? "open" : "closed"}`}>
                  <Icon name={item.allowed ? "unlock" : "lock"} />
                  <span>{item.label}</span>
                  <strong>{item.stateText}</strong>
                </div>
              )}
            </For>
          </div>
        </section>
      </section>
    </PageScaffold>
  );
}
