import { useComputed, type ReadonlySignal } from "@preact/signals";
import { ProgressState } from "../types/ProgressState";

export interface ProgressBarProps {
  progress: ReadonlySignal<ProgressState>;
}

export function ProgressBar({ progress }: ProgressBarProps) {
  const className = useComputed(
    () => {
      const pg = progress.value;
      let cls = "progress-bar progress-bar-striped";
      if (pg.currentValue === undefined) {
        cls += " visually-hidden";
      } else if (pg.finished) {
        cls += pg.error ? " bg-warning text-dark" : " bg-success";
      } else {
        cls  += " bg-info progress-bar-animated";
      }
      return cls;
    }
  );
  const pct = useComputed<string>(
    () => {
      const { minValue, maxValue, currentValue } = progress.value;
      return `${(100 * (currentValue - minValue)) / Math.max(1, maxValue - minValue)}%`;
    });
  const style = useComputed(() => ({
    width: pct.value,
  }));

  return (
    <div>
      <div
        className={className}
        style={style}
        role="progressbar"
        aria-valuenow={progress.value.currentValue}
        aria-valuemin={progress.value.minValue}
        aria-valuemax={progress.value.maxValue}>
        {pct}
      </div>
      <div className="progress-text">{progress.value.text}</div>
    </div>
  );
}
