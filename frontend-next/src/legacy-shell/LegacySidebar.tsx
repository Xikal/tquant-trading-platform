import { For } from "solid-js";
import { Link } from "@tanstack/solid-router";
import type { LegacyNavIcon, LegacyNavItem } from "./legacyNavConfig";
import { nextRoutes } from "../shared/config/routes";
import { sidebarInnerStyle } from "./legacyShellStyles";

export function LegacySidebar(props: {
  items: LegacyNavItem[];
  currentPath: string;
  mobileOpen: boolean;
  onNavigate: () => void;
}) {
  const sidebarClass = () => [
    "legacy-sidebar",
    "tq-sidebar",
    props.mobileOpen ? "legacy-sidebar--mobile-open tq-sidebar--mobile-open" : "",
  ].filter(Boolean).join(" ");

  return (
    <aside class={sidebarClass()} aria-label="主导航">
      <div style={sidebarInnerStyle}>
        <div class="legacy-sidebar__brand">维斯量化</div>
        <nav class="legacy-sidebar__nav">
          <For each={props.items}>
            {(item) => (
              <Link
                to={item.path}
                class={`legacy-sidebar__item${isActivePath(props.currentPath, item.path) ? " legacy-sidebar__item--active" : ""}`}
                title={item.label}
                onClick={() => props.onNavigate()}
                onPointerUp={() => props.onNavigate()}
              >
                <LegacyIcon name={item.icon} />
                <span>{item.label}</span>
              </Link>
            )}
          </For>
        </nav>
        <div class="legacy-sidebar__footer" aria-hidden="true">
          <span class="legacy-sidebar__collapse-mark">≡</span>
        </div>
      </div>
    </aside>
  );
}

function isActivePath(currentPath: string, itemPath: string): boolean {
  const route = nextRoutes.find((item) => item.path === itemPath);
  const candidates = route ? [route.path, route.legacyPath] : [itemPath];
  if (itemPath === "/next/monitor") return candidates.includes(currentPath);
  if (candidates.includes(currentPath)) return true;
  return currentPath === itemPath || currentPath.startsWith(`${itemPath}/`);
}

function LegacyIcon(props: { name: LegacyNavIcon }) {
  return (
    <span class={`legacy-sidebar__icon legacy-sidebar__icon--${props.name}`} aria-hidden="true">
      <svg viewBox="0 0 16 16" aria-hidden="true">
        {iconPath(props.name)}
      </svg>
    </span>
  );
}

function iconPath(name: LegacyNavIcon) {
  switch (name) {
    case "fund":
      return <path d="M2.5 12.5h11v1h-11v-1Zm1-2.2 2.7-2.7 2.1 1.6 3.3-4.1.8.6-4 5-2.1-1.6-2.1 2.1-.7-.9ZM3 3h10v1H3V3Z" />;
    case "line":
      return <path d="M2.5 12.5h11v1h-11v-1Zm1-2.1 2.5-3 2.1 1.4 3.5-4.5.8.6-4.1 5.3-2.1-1.4-1.9 2.3-.8-.7Z" />;
    case "read":
      return <path d="M2.5 3.2h4.8c.6 0 1 .2 1.2.5.2-.3.6-.5 1.2-.5h3.8v9.9H9.6c-.5 0-.8.2-1.1.5-.3-.3-.6-.5-1.1-.5H2.5V3.2Zm1 1v7.9h3.8c.3 0 .5.1.7.2V4.5c-.1-.2-.3-.3-.7-.3H3.5Zm5.5.3v7.8c.2-.1.4-.2.7-.2h2.8V4.2H9.7c-.4 0-.6.1-.7.3Z" />;
    case "aim":
      return <path d="M7.5 1.8h1v2.1a4.2 4.2 0 0 1 3.6 3.6h2.1v1h-2.1a4.2 4.2 0 0 1-3.6 3.6v2.1h-1v-2.1a4.2 4.2 0 0 1-3.6-3.6H1.8v-1h2.1a4.2 4.2 0 0 1 3.6-3.6V1.8Zm.5 3.1a3.1 3.1 0 1 0 0 6.2 3.1 3.1 0 0 0 0-6.2Zm0 1.8a1.3 1.3 0 1 1 0 2.6 1.3 1.3 0 0 1 0-2.6Z" />;
    case "experiment":
      return <path d="M5.5 2.5h5v1h-1v3.1l3.1 5.4c.5.9-.1 2-1.1 2h-7c-1 0-1.6-1.1-1.1-2l3.1-5.4V3.5h-1v-1Zm2 1v3.4l-3.2 5.6c-.1.2 0 .5.2.5h7c.2 0 .3-.3.2-.5L8.5 6.9V3.5h-1Z" />;
    case "database":
      return <path d="M8 2.2c3 0 5.2.9 5.2 2.1v7.4c0 1.2-2.2 2.1-5.2 2.1s-5.2-.9-5.2-2.1V4.3c0-1.2 2.2-2.1 5.2-2.1Zm0 1c-2.6 0-4.2.7-4.2 1.1S5.4 5.4 8 5.4s4.2-.7 4.2-1.1S10.6 3.2 8 3.2Zm4.2 3c-.9.7-2.4 1.1-4.2 1.1s-3.3-.4-4.2-1.1v2.4c0 .4 1.6 1.1 4.2 1.1s4.2-.7 4.2-1.1V6.2Zm0 4.1c-.9.7-2.4 1.1-4.2 1.1s-3.3-.4-4.2-1.1v1.4c0 .4 1.6 1.1 4.2 1.1s4.2-.7 4.2-1.1v-1.4Z" />;
    case "setting":
      return <path d="m8 1.8 1 .3.3 1.4c.4.1.7.3 1 .5l1.4-.5.7.8-.6 1.3c.2.3.4.7.5 1.1l1.3.5v1l-1.3.5c-.1.4-.3.8-.5 1.1l.6 1.3-.7.8-1.4-.5c-.3.2-.6.4-1 .5l-.3 1.4H7l-.3-1.4c-.4-.1-.7-.3-1-.5l-1.4.5-.7-.8.6-1.3c-.2-.3-.4-.7-.5-1.1l-1.3-.5v-1l1.3-.5c.1-.4.3-.8.5-1.1l-.6-1.3.7-.8 1.4.5c.3-.2.6-.4 1-.5L7 2.1l1-.3Zm0 4A2.2 2.2 0 1 0 8 10.2 2.2 2.2 0 0 0 8 5.8Z" />;
  }
}
