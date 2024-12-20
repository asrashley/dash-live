import { JSX } from 'preact';
import { type Signal } from '@preact/signals';

import { DataListInput } from './DataListInput.js';
import { MultiSelectInput } from './MultiSelectInput.js';
import { RadioInput } from './RadioInput.js';
import { SelectInput } from './SelectInput.js';
import { SelectOptionType } from '../types/SelectOptionType.js';

export interface InputProps extends Omit<JSX.InputHTMLAttributes<HTMLInputElement>, 'className' | 'name' | 'value'> {
  className?: string;
  datalist_type?: 'text' | 'number'
  error?: string;
  name: string;
  options?: SelectOptionType[];
  value: Signal<number | string | boolean>;
  validation: "was-validated" | "has-validation" | "needs-validation";
  setValue: (name: string, value: string | boolean) => void;
}

export function Input({
  className = "",
  datalist_type,
  type,
  name,
  value,
  setValue,
  error,
  validation,
  title,
  options,
}: InputProps) {
  const inputClass =
    type === "checkbox"
      ? "form-check-input"
      : type === "select"
      ? "form-select"
      : "form-control";
  const validationClass = error
    ? " is-invalid"
    : validation === "was-validated"
    ? " is-valid"
    : "";
  const inpProps = {
    name,
    type,
    className: `${inputClass}${validationClass} ${className}`,
    title,
    id: `model-${name}`,
    value: typeof value.value === "number" ? value.value : `${value.value}`,
    "aria-describedby": `field-${name}`,
    onInput: (ev) => {
      const { target } = ev;
      setValue(name, target.type === "checkbox" ? target.checked : target.value);
    },
  };
  switch (type) {
    case "radio":
      return <RadioInput setValue={setValue} options={options} {...inpProps} />;
    case "select":
      return <SelectInput options={options} {...inpProps} />;
    case "multiselect":
      return <MultiSelectInput setValue={setValue} options={options} {...inpProps} />;
    case "datalist":
      inpProps.type = datalist_type ?? 'text';
      return <DataListInput options={options} {...inpProps} />;
    case 'checkbox':
      return <input checked={value.value === true || value.value === "1"} {...inpProps} />;
    default:
      return <input {...inpProps} />;
  }
}
