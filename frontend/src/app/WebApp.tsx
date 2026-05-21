import { RouterProvider } from "react-router";
import { webRouter } from "./router/webRoutes";

export function WebApp() {
  return <RouterProvider router={webRouter} />;
}
