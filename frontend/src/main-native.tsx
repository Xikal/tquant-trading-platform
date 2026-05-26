import React from "react";
import ReactDOM from "react-dom/client";
import "antd-mobile/es/global";
import { AppProviders } from "./app/AppProviders";
import { NativeApp } from "./app/NativeApp";
import "./styles/foundation/tokens.css";
import "./styles/mobile/native-app.css";
import "./styles/mobile/native-auth.css";
import "./styles/mobile/native-preview-cards.css";
import "./styles/mobile/native-sheets.css";
import "./styles/mobile/native-holdings.css";
import "./styles/mobile/native-holdings-editor.css";
import "./styles/mobile/native-design-sync.css";
import "./styles/mobile/native-design-metrics.css";
import "./styles/mobile/native-design-tabs.css";
import "./styles/mobile/native-settings-sheet.css";
import "./styles/mobile/native-ux-clarity.css";

if (typeof document !== "undefined") {
  document.body.classList.add("native-app-mode");
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProviders>
      <NativeApp />
    </AppProviders>
  </React.StrictMode>
);
