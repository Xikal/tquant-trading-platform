import React from "react";
import ReactDOM from "react-dom/client";
import MobileApp from "./mobile/MobileApp";
import "./styles/native-index.css";

if (typeof document !== "undefined") {
  document.body.classList.add("native-app-mode");
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MobileApp />
  </React.StrictMode>
);
