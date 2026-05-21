import { lazy, Suspense } from "react";
import { createMemoryRouter } from "react-router";

const MobileApp = lazy(async () => ({ default: (await import("../../mobile/MobileApp")).default }));

export const nativeRouter = createMemoryRouter([
  {
    path: "*",
    element: (
      <Suspense fallback={<div className="mobile-error-state">App 加载中...</div>}>
        <MobileApp />
      </Suspense>
    ),
    errorElement: <div className="mobile-error-state">App 页面加载失败，请返回首页后重试。</div>,
  },
]);
