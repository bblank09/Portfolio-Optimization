import { useEffect, useRef, useState } from "react";

const DEFAULT_STAGES = ["Validating inputs", "Loading SEC NAV cache", "Computing backtest", "Preparing report"];
const DEFAULT_TITLE = "Running backtest…";

interface Props {
  open: boolean;
  // Both optional so the original BacktestWorkspace caller is unaffected --
  // OptimizeWorkspace passes optimizer-specific copy instead.
  title?: string;
  stages?: string[];
}

export function RunOverlay({ open, title = DEFAULT_TITLE, stages = DEFAULT_STAGES }: Props) {
  const [activeStage, setActiveStage] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) {
      setActiveStage(0);
      previousFocusRef.current?.focus();
      return;
    }
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panelRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>("button, a[href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])"));
      if (!focusable.length) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    const interval = setInterval(() => {
      setActiveStage((current) => Math.min(stages.length - 1, current + 1));
    }, 450);
    return () => {
      clearInterval(interval);
      document.removeEventListener("keydown", handleKeyDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  return (
    <div aria-busy="true" aria-labelledby="run-overlay-title" className="run-overlay open" role="dialog" aria-modal="true">
      <div aria-describedby="run-overlay-status" className="run-panel" ref={panelRef} tabIndex={-1}>
        <h4 id="run-overlay-title">{title}</h4>
        <p aria-live="polite" className="srOnly" id="run-overlay-status">{stages[activeStage]}</p>
        <div className="run-steps">
          {stages.map((stage, index) => (
            <div aria-current={index === activeStage ? "step" : undefined} className={index < activeStage ? "run-step done" : index === activeStage ? "run-step active" : "run-step"} key={stage}>
              <span className="marker" /> {stage}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
