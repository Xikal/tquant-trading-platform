import type { JSX } from "solid-js";
import { render } from "solid-js/web";
import { AppProviders } from "../../app/AppProviders";

export function renderWithProviders(node: () => JSX.Element, container: HTMLElement) {
  return render(() => <AppProviders>{node()}</AppProviders>, container);
}
