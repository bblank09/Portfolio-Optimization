import { useEffect, useState } from "react";

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

  useEffect(() => {
    if (!open) {
      setActiveStage(0);
      return;
    }
    const interval = setInterval(() => {
      setActiveStage((current) => Math.min(stages.length - 1, current + 1));
    }, 450);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  return (
    <div className="run-overlay open">
      <div className="run-panel">
        <h4>{title}</h4>
        <div className="run-steps">
          {stages.map((stage, index) => (
            <div className={index < activeStage ? "run-step done" : index === activeStage ? "run-step active" : "run-step"} key={stage}>
              <span className="marker" /> {stage}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
