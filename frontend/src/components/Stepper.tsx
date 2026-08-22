const STEP_LABELS = ["Portfolio", "Assumptions", "Results"];

interface Props {
  currentStep: number;
  unlockedStep: number;
  onStepClick: (index: number) => void;
}

export function Stepper({ currentStep, unlockedStep, onStepClick }: Props) {
  return (
    <>
      <div className="stepper">
        {STEP_LABELS.map((label, index) => (
          <StepItem key={label} index={index} label={label} currentStep={currentStep} unlockedStep={unlockedStep} onStepClick={onStepClick} />
        ))}
      </div>
      <div className="stepper-compact">
        Step <b>{currentStep + 1}</b> of {STEP_LABELS.length} &middot; {STEP_LABELS[currentStep]}
      </div>
    </>
  );
}

function StepItem({
  index,
  label,
  currentStep,
  unlockedStep,
  onStepClick
}: {
  index: number;
  label: string;
  currentStep: number;
  unlockedStep: number;
  onStepClick: (index: number) => void;
}) {
  const locked = index > unlockedStep;
  const done = index < currentStep || (index <= unlockedStep && index < currentStep);
  const classNames = [
    "step",
    index === currentStep ? "active" : "",
    done ? "done" : "",
    locked ? "locked" : ""
  ].filter(Boolean).join(" ");

  return (
    <>
      {index > 0 ? <div className="step-sep" /> : null}
      <button
        aria-current={index === currentStep ? "step" : undefined}
        className={classNames}
        disabled={locked}
        onClick={() => onStepClick(index)}
        type="button"
      >
        <span className="dot">{index + 1}</span>{label}
      </button>
    </>
  );
}
