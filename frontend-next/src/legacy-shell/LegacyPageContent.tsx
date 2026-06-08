import type { JSX } from "solid-js";
import { contentInnerArtifactStyle, contentInnerStyle, contentMainArtifactStyle, contentMainStyle } from "./legacyShellStyles";

export function LegacyPageContent(props: { children: JSX.Element; variant?: "workspace" | "artifact" }) {
  const isArtifact = () => props.variant === "artifact";
  return (
    <main class={`legacy-main${isArtifact() ? " legacy-main--artifact" : ""}`} style={isArtifact() ? contentMainArtifactStyle : contentMainStyle}>
      <div class="legacy-main__inner" style={isArtifact() ? contentInnerArtifactStyle : contentInnerStyle}>
        {props.children}
      </div>
    </main>
  );
}
