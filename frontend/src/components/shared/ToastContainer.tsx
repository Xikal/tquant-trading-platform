import type { CSSProperties, ReactNode } from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef } from "react";
import { useSharedUiStore, type ToastMessage } from "../../stores/sharedUiStore";

interface ToastContextValue {
  pushToast: (message: Omit<ToastMessage, "id">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_STACK_STYLE: CSSProperties = {
  bottom: 22,
  display: "flex",
  flexDirection: "column",
  gap: 10,
  position: "fixed",
  right: 22,
  width: "min(360px, calc(100vw - 32px))",
  zIndex: 1000,
};

const TOAST_BASE_STYLE: CSSProperties = {
  background: "#fff",
  border: "1px solid #dbe3ef",
  borderRadius: 14,
  boxShadow: "0 16px 36px rgba(15, 23, 42, 0.16)",
  color: "#0f172a",
  display: "flex",
  flexDirection: "column",
  gap: 4,
  padding: "12px 38px 12px 14px",
  position: "relative",
};

const TOAST_TONE_STYLES: Record<NonNullable<ToastMessage["tone"]>, CSSProperties> = {
  success: { borderLeft: "4px solid #16a34a" },
  warning: { borderLeft: "4px solid #d97706" },
  error: { borderLeft: "4px solid #dc2626" },
  info: { borderLeft: "4px solid #2563eb" },
};

const TOAST_CLOSE_STYLE: CSSProperties = {
  background: "transparent",
  border: 0,
  color: "#64748b",
  cursor: "pointer",
  fontSize: 18,
  position: "absolute",
  right: 10,
  top: 8,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const messages = useSharedUiStore((state) => state.toasts);
  const addToast = useSharedUiStore((state) => state.addToast);
  const removeStoredToast = useSharedUiStore((state) => state.removeToast);
  const timers = useRef<number[]>([]);

  const removeToast = useCallback((id: string) => {
    removeStoredToast(id);
  }, [removeStoredToast]);

  const pushToast = useCallback((message: Omit<ToastMessage, "id">) => {
    const id = addToast(message);
    if (!message.sticky) {
      timers.current.push(window.setTimeout(() => removeToast(id), message.tone === "error" || message.tone === "warning" ? 6000 : 3500));
    }
  }, [addToast, removeToast]);

  useEffect(() => () => {
    timers.current.forEach((timer) => window.clearTimeout(timer));
    timers.current = [];
  }, []);

  const value = useMemo(() => ({ pushToast, removeToast }), [pushToast, removeToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div style={TOAST_STACK_STYLE}>
        {messages.map((message) => (
          <div key={message.id} style={{ ...TOAST_BASE_STYLE, ...TOAST_TONE_STYLES[message.tone ?? "info"] }} role="alert" aria-live="polite">
            <button type="button" onClick={() => removeToast(message.id)} aria-label="关闭提示" style={TOAST_CLOSE_STYLE}>×</button>
            <strong>{message.title}</strong>
            {message.description ? <span>{message.description}</span> : null}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    return { pushToast: () => undefined, removeToast: () => undefined };
  }
  return context;
}
