import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "antd/dist/reset.css";
import { AppProviders } from "./app/AppProviders";
import { WebApp } from "./app/WebApp";
import { WebUiProviders } from "./app/WebUiProviders";
import "./styles/workspace/workspace.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProviders>
      <WebUiProviders>
        <WebApp />
      </WebUiProviders>
    </AppProviders>
  </StrictMode>
);

void import("./registerServiceWorker").then((module) => module.registerServiceWorker());
