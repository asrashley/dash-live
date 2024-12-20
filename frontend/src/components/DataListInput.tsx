import { Fragment, type JSX } from "preact";
import { SelectOptionType } from "../types/SelectOptionType";

export interface DataListInputProps extends JSX.InputHTMLAttributes<HTMLInputElement> {
  name: string;
  options: SelectOptionType[];
  className?: string;
}

export function DataListInput({ className = "", name, options, ...props }: DataListInputProps) {
  return (
    <Fragment>
      <input
        className={className}
        name={name}
        list={`list-${name}`}
        {...props}
      />
      <datalist id={`list-${name}`}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} selected={opt.selected}>
            {opt.title}
          </option>
        ))}
      </datalist>
    </Fragment>
  );
}
