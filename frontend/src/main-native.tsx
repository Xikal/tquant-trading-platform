import React from "react";
import ReactDOM from "react-dom/client";
import "antd-mobile/es/global";
import { AppProviders } from "./app/AppProviders";
import { NativeApp } from "./app/NativeApp";
import "./styles/native-index.css";
import "./ui/theme/mobileTheme.css";
import "./ui/theme/tokens.css";

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
