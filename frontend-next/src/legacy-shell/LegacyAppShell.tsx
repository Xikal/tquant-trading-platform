import { createSignal, onCleanup, onMount, type JSX } from "solid-js";
import { useLocation, useNavigate } from "@tanstack/solid-router";
import { useAuth } from "../features/auth/authModel";
import { CommandPalette } from "../features/trading-workspace/CommandPalette";
import { nextRoutes } from "../shared/config/routes";
import { exposeTelemetryForDiagnostics, recordTelemetry } from "../shared/telemetry/clientTelemetry";
import { installWorkspaceShortcuts } from "../app/keyboardShortcuts";
import { LegacyPageContent } from "./LegacyPageContent";
import { LegacySidebar } from "./LegacySidebar";
import { LegacyTopbar } from "./LegacyTopbar";
import { legacyNavItems } from "./legacyNavConfig";
import { contentColumnStyle, workspaceShellStyle } from "./legacyShellStyles";

export function LegacyAppShell(props: { children: JSX.Element }) {
  const location = useLocation();
  const navigate = useNavigate();
  const auth = useAuth();
  const [commandOpen, setCommandOpen] = createSignal(false);
  const [mobileNavOpen, setMobileNavOpen] = createSignal(false);
  const [online, setOnline] = createSignal(typeof navigator === "undefined" ? true : navigator.onLine);
  const currentRoute = () => nextRoutes.find((route) => route.path === location().pathname || route.legacyPath === location().pathname) ?? nextRoutes[0];
  const shellVariant = () => (currentRoute().page === "monitor" ? "artifact" : "workspace");

  onMount(() => {
    exposeTelemetryForDiagnostics();
    const cleanup = installWorkspaceShortcuts({
      navigate,
      openCommandPalette: () => {
        recordTelemetry({ kind: "ui", name: "command-palette-open", status: "shortcut" });
        setCommandOpen(true);
      },
    });
    onCleanup(cleanup);
  });

  onMount(() => {
    const updateNetworkState = () => setOnline(typeof navigator === "undefined" ? true : navigator.onLine);
    updateNetworkState();
    window.addEventListener("online", updateNetworkState);
    window.addEventListener("offline", updateNetworkState);
    onCleanup(() => {
      window.removeEventListener("online", updateNetworkState);
      window.removeEventListener("offline", updateNetworkState);
    });
  });

  return (
    <div class={`legacy-workspace-shell legacy-workspace-shell--${shellVariant()} tq-app`} style={workspaceShellStyle}>
      <LegacySidebar
        items={legacyNavItems}
        currentPath={location().pathname}
        mobileOpen={mobileNavOpen()}
        onNavigate={() => setMobileNavOpen(false)}
      />
      <div class="legacy-content-column" style={contentColumnStyle}>
        <LegacyTopbar
          currentRoute={currentRoute()}
          auth={auth}
          online={online()}
          onOpenNav={() => setMobileNavOpen(true)}
          onOpenCommand={() => setCommandOpen(true)}
        />
        <LegacyPageContent variant={shellVariant()}>{props.children}</LegacyPageContent>
      </div>
      <div
        class={`legacy-mobile-scrim tq-mobile-scrim${mobileNavOpen() ? " legacy-mobile-scrim--open tq-mobile-scrim--open" : ""}`}
        onClick={() => setMobileNavOpen(false)}
        aria-hidden="true"
      />
      <CommandPalette open={commandOpen()} onClose={() => setCommandOpen(false)} />
    </div>
  );
}
