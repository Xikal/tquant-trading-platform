import { createBrowserRouter } from "react-router";
import { webRoutes } from "./webRouteDefinitions";

export { webRoutes } from "./webRouteDefinitions";

export const webRouter = createBrowserRouter(webRoutes);
