import React from "react";
import ReactDOM from "react-dom/client";
import "antd/dist/reset.css";
import { AppProviders } from "./app/AppProviders";
import { WebApp } from "./app/WebApp";
import { WebUiProviders } from "./app/WebUiProviders";
import "./styles/workspace/workspace.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProviders>
      <WebUiProviders>
        <WebApp />
      </WebUiProviders>
    </AppProviders>
  </React.StrictMode>
);

void import("./registerServiceWorker").then(({ registerServiceWorker }) => {
  registerServiceWorker();
});
