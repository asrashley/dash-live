import { ComponentChildren, Fragment, JSX } from "preact";

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
  return (
    <Fragment>
      <input
        className={`form-check-input ${inputClass}`}
        type="checkbox"
        id={`check_${name}`}
        name={name}
        {...props}
      />
      <label className={`form-check-label ${labelClass}`} for={`check_${name}`}>
        {label}
      </label>
      {children}
    </Fragment>
  );
}
