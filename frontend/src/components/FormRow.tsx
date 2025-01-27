import { type ComponentChildren } from "preact";

interface FormTextProps {
  text?: string;
  className?: string;
}
function FormText({text, className}: FormTextProps) {
  if (!text) {
    return null;
  }
  return <div className={`${className} form-text`}>{text}</div>;
}

interface ErrorFeedbackProps {
  error?: string;
}
function ErrorFeedback({error}: ErrorFeedbackProps) {
  if (!error) {
    return null;
  }
  return <div className="invalid-feedback" style="display:block">{error}</div>;
}

export interface FormRowProps {
  name: string;
  label: string;
  children: ComponentChildren;
  className?: string;
  text?: string;
  error?: string;
  layout?: number[];
}
export function FormRow({ className = "", name, layout, label, text, children, error }: FormRowProps) {
  // eslint-disable-next-line prefer-const
  let [left, middle, right] = layout ?? [2, 7, 3];
  if (!text) {
    middle += right;
  }
  return <div className={`row mb-2 form-group ${className}`}>
      <label className={`col-${left} col-form-label`} htmlFor={`model-${name}`}>{label}:</label>
      <div className={`col-${middle}`}>{children}</div>
      <FormText text={text} className={`col-${right}`} />
      <ErrorFeedback error={error} />
    </div>;
}
