import { render } from "solid-js/web";
import { App } from "./app/App";
import "./shared/styles/tokens.css";
import "./shared/styles/legacy-workspace.css";
import "./shared/styles/legacy-solid-adapter.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("frontend-next root element is missing");
}

render(() => <App />, root);
