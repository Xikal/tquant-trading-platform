import { createContext, useCallback, useContext, useEffect, useMemo, useRef, type ReactNode } from "react";
import { useSharedUiStore, type ToastMessage } from "../../stores/sharedUiStore";

interface ToastContextValue {
  pushToast: (message: Omit<ToastMessage, "id">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

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
      <div className="tq-toast-stack">
        {messages.map((message) => (
          <div key={message.id} className={`tq-toast tq-toast--${message.tone ?? "info"}`} role="alert" aria-live="polite">
            <button type="button" onClick={() => removeToast(message.id)} aria-label="关闭提示">×</button>
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
