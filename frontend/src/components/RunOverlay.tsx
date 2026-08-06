import { useEffect, useState } from "react";

const STAGES = ["Validating inputs", "Loading SEC NAV cache", "Computing backtest", "Preparing report"];

interface Props {
  open: boolean;
}

export function RunOverlay({ open }: Props) {
  const [activeStage, setActiveStage] = useState(0);

  useEffect(() => {
    if (!open) {
      setActiveStage(0);
      return;
    }
    const interval = setInterval(() => {
      setActiveStage((current) => Math.min(STAGES.length - 1, current + 1));
    }, 450);
    return () => clearInterval(interval);
  }, [open]);

  if (!open) return null;

  return (
    <div className="run-overlay open">
      <div className="run-panel">
        <h4>Running backtest&hellip;</h4>
        <div className="run-steps">
          {STAGES.map((stage, index) => (
            <div className={index < activeStage ? "run-step done" : index === activeStage ? "run-step active" : "run-step"} key={stage}>
              <span className="marker" /> {stage}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
