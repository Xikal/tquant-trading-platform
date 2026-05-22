import React from "react";
import ReactDOM from "react-dom/client";
import "antd/dist/reset.css";
import { AppProviders } from "./app/AppProviders";
import { WebApp } from "./app/WebApp";
import { WebUiProviders } from "./app/WebUiProviders";
import { registerServiceWorker } from "./registerServiceWorker";
import "./styles/index.css";

registerServiceWorker();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProviders>
      <WebUiProviders>
        <WebApp />
      </WebUiProviders>
    </AppProviders>
  </React.StrictMode>
);
