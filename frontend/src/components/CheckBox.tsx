import { type ComponentChildren, Fragment, type JSX } from "preact";

export interface CheckBoxProps extends JSX.InputHTMLAttributes<HTMLInputElement> {
  name: string;
  label: string;
  inputClass?: string;
  labelClass?: string;
  children?: ComponentChildren;
}

export function CheckBox({
  name,
  label,
  inputClass = "col-2",
  labelClass = "col-6",
  children,
  ...props
}: CheckBoxProps) {
  const id = `check_${name}`;
  return (
    <Fragment>
      <input
        className={`form-check-input ${inputClass}`}
        type="checkbox"
        id={id}
        name={name}
        {...props}
      />
      <label className={`form-check-label ${labelClass}`} for={id}>
        {label}
      </label>
      {children}
    </Fragment>
  );
}
