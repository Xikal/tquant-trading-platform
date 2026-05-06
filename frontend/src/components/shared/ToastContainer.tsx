import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export type ToastTone = "info" | "success" | "warning" | "error";

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  tone?: ToastTone;
  sticky?: boolean;
}

interface ToastContextValue {
  pushToast: (message: Omit<ToastMessage, "id">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([]);
  const timers = useRef<number[]>([]);

  const removeToast = useCallback((id: string) => {
    setMessages((current) => current.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback((message: Omit<ToastMessage, "id">) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const next = { ...message, id };
    setMessages((current) => [next, ...current].slice(0, 3));
    if (!message.sticky) {
      timers.current.push(window.setTimeout(() => removeToast(id), message.tone === "error" || message.tone === "warning" ? 6000 : 3500));
    }
  }, [removeToast]);

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
