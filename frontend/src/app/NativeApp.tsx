import { RouterProvider } from "react-router";
import { nativeRouter } from "./router/nativeRoutes";

export function NativeApp() {
  return <RouterProvider router={nativeRouter} />;
}
