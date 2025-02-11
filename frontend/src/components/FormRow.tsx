import { type ComponentChildren } from "preact";
import { useComputed, type ReadonlySignal } from "@preact/signals";

interface FormTextProps {
  id?: string;
  text?: string;
  className?: string;
}
function FormText({id, text, className}: FormTextProps) {
  if (!text) {
    return null;
  }
  return <div id={id} className={`${className} form-text`}>{text}</div>;
}

interface ErrorFeedbackProps {
  error?: ReadonlySignal<string|undefined>;
}
function ErrorFeedback({error}: ErrorFeedbackProps) {
  const className = useComputed<string>(() => `invalid-feedback ${error?.value ? "d-block": "d-none"}`);
  return <div className={className}>{error}</div>;
}

export interface FormRowProps {
  name: string;
  label?: string;
  children: ComponentChildren;
  className?: string;
  inline?: boolean;
  text?: string;
  error?: ReadonlySignal<string|undefined>;
  layout?: number[];
}
export function FormRow({ className = "", name, layout, label, inline, text, children, error }: FormRowProps) {
  // eslint-disable-next-line prefer-const
  let [left, middle, right] = layout ?? [2, 7, 3];
  const rowClassName = `row mb-2 form-group ${className}${inline ? " form-check-inline": ""}`;

  if (!label) {
    middle += left;
  }
  if (!text) {
    middle += right;
  }
  return <div className={rowClassName}>
      {label ? <label id={`label-${name}`} className={`col-${left} col-form-label`} htmlFor={`model-${name}`}>{label}:</label> : ""}
      <div className={`col-${middle}`}>{children}</div>
      <FormText id={`text-${name}`} text={text} className={`col-${right}`} />
      <ErrorFeedback error={error} />
    </div>;
}
