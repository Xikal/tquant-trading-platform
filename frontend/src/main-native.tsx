import React from "react";
import ReactDOM from "react-dom/client";
import "antd-mobile/es/global";
import { AppProviders } from "./app/AppProviders";
import { NativeApp } from "./app/NativeApp";
import "./styles/foundation/tokens.css";
import "./styles/mobile/native-app.css";
import "./styles/mobile/native-auth.part-1.css";
import "./styles/mobile/native-auth.part-2.css";
import "./styles/mobile/native-preview-cards.part-1.css";
import "./styles/mobile/native-preview-cards.part-2.css";
import "./styles/mobile/native-sheets.part-1.css";
import "./styles/mobile/native-sheets.part-2.css";
import "./styles/mobile/native-holdings.part-1.css";
import "./styles/mobile/native-holdings.part-2.css";
import "./styles/mobile/native-holdings-editor.css";
import "./styles/mobile/native-design-sync.part-1.css";
import "./styles/mobile/native-design-sync.part-2.css";
import "./styles/mobile/native-design-metrics.part-1.css";
import "./styles/mobile/native-design-metrics.part-2.css";
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
