import { useComputed } from "@preact/signals";

import { ProgressBar } from "./ProgressBar";
import {
  UseValidatorWebsocketHook,
  ValidatorState,
} from "../hooks/useValidatorWebsocket";

const stateClassMap = {
  [ValidatorState.IDLE]: "text-bg-secondary",
  [ValidatorState.ACTIVE]: "bg-success-subtle text-dark",
  [ValidatorState.CANCELLING]: "bg-danger",
  [ValidatorState.CANCELLED]: "bg-warning-subtle text-dark",
  [ValidatorState.DONE]: "bg-success",
};

export interface ProgressBarWithStateProps {
  progress: UseValidatorWebsocketHook["progress"];
  state: UseValidatorWebsocketHook["state"];
}
export function ProgressBarWithState({
  progress,
  state,
}: ProgressBarWithStateProps) {
  const stateClass = useComputed<string>(
    () =>
      `position-absolute top-0 start-50 translate-middle badge rounded-pill ${
        stateClassMap[state.value]
      }`
  );

  return (
    <div className="position-relative">
      <div className="card progress">
        <ProgressBar progress={progress} />
      </div>
      <div className={stateClass} data-testid="validator-state-badge">{state}</div>
    </div>
  );
}
