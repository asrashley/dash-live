import { useCallback } from "preact/hooks";
import { type ReadonlySignal } from "@preact/signals";
import { BootstrapLevels } from "../types/BootstrapLevels";

export interface AlertProps {
  id: number;
  text: string | ReadonlySignal<string>;
  level: BootstrapLevels;
  onDismiss?: (id: number) => void;
}

export function Alert({ text, level, onDismiss, id }: AlertProps) {
  const dismiss = useCallback(() => {
    onDismiss(id);
  }, [id, onDismiss]);
  const className = `alert alert-${level} ${
    onDismiss ? "alert-dismissible fade " : ""
  }show`;
  return (
    <div className={className} id={`alert_${id}`} role="alert">
      {text}
      {onDismiss ? (
        <button
          type="button"
          className="btn-close"
          aria-label="Close"
          onClick={dismiss}
         />
      ) : null}
    </div>
  );
}
