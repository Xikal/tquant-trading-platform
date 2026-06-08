import type { JSX } from "solid-js";
import { LegacyAppShell } from "../legacy-shell/LegacyAppShell";

export function AppShell(props: { children: JSX.Element }) {
  return <LegacyAppShell>{props.children}</LegacyAppShell>;
}
