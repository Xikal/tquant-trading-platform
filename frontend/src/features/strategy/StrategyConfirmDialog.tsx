import { useEffect, useId, useRef } from "react";

export function StrategyConfirmDialog({
  loading,
  title,
  description,
  onCancel,
  onConfirm,
}: {
  loading: boolean;
  title: string;
  description: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const confirmRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    cancelRef.current?.focus();
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab") return;
      const targets = [cancelRef.current, confirmRef.current].filter(Boolean) as HTMLButtonElement[];
      if (!targets.length) return;
      const currentIndex = targets.indexOf(document.activeElement as HTMLButtonElement);
      const nextIndex = event.shiftKey
        ? (currentIndex <= 0 ? targets.length - 1 : currentIndex - 1)
        : (currentIndex >= targets.length - 1 ? 0 : currentIndex + 1);
      event.preventDefault();
      targets[nextIndex]?.focus();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  return (
    <div className="strategy-dialog-backdrop" role="presentation">
      <section className="strategy-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <h2 id={titleId}>{title}</h2>
        <p>{description}</p>
        <div className="strategy-dialog-actions">
          <button ref={cancelRef} type="button" onClick={onCancel} disabled={loading}>取消</button>
          <button ref={confirmRef} type="button" className="primary" onClick={onConfirm} disabled={loading}>
            {loading ? "提交中" : "确认提交"}
          </button>
        </div>
      </section>
    </div>
  );
}
