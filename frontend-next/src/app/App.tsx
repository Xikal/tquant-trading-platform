import { RouterProvider, createRouter, parseSearchWith, stringifySearchWith } from "@tanstack/solid-router";
import { AppProviders } from "./AppProviders";
import { AppErrorBoundary } from "./ErrorBoundary";
import { routeTree } from "./routeTree";

const router = createRouter({
  routeTree,
  scrollRestoration: true,
  parseSearch: parseSearchWith((value) => value),
  stringifySearch: stringifySearchWith(JSON.stringify),
});

declare module "@tanstack/solid-router" {
  interface Register {
    router: typeof router;
  }
}

export function App() {
  return (
    <AppProviders>
      <AppErrorBoundary>
        <RouterProvider router={router} />
      </AppErrorBoundary>
    </AppProviders>
  );
}
