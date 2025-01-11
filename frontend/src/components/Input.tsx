import { type ReadonlySignal } from '@preact/signals';

import { DataListInput } from './DataListInput';
import { MultiSelectInput } from './MultiSelectInput';
import { RadioInput } from './RadioInput';
import { SelectInput } from './SelectInput';
import { SelectOptionType } from '../types/SelectOptionType';
import { SetValueFunc } from '../types/SetValueFunc';
import { FormInputItem } from '../types/FormInputItem';

export interface InputProps extends FormInputItem {
  value: ReadonlySignal<number | string | boolean>;
  validation?: "was-validated" | "has-validation" | "needs-validation";
  setValue: SetValueFunc;
}

type BaseInputProps = {
  name: string;
  id: string;
  type: FormInputItem["type"];
  className: string;
  title: string;
  value: string;
  "aria-describedby": string;
  onInput: (ev: Event) => void;
};

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
  const inpProps: BaseInputProps = {
    name,
    type,
    className: `${inputClass}${validationClass} ${className}`,
    title,
    id: `model-${name}`,
    value: typeof value.value === "string" ? value.value : `${value.value}`,
    "aria-describedby": `field-${name}`,
    onInput: (ev: Event) => {
      const target = ev.target as HTMLInputElement;
      setValue(name, target.type === "checkbox" ? target.checked : target.value);
    },
  };
  switch (type) {
    case "radio":
      return <RadioInput setValue={setValue} options={options} {...inpProps} />;
    case "select":
      return <SelectInput setValue={setValue} options={options} {...inpProps} />;
    case "multiselect":
      return <MultiSelectInput setValue={setValue} options={options} {...inpProps} />;
    case "datalist":
      inpProps.type = datalist_type ?? 'text';
      return <DataListInput options={options as SelectOptionType[]} {...inpProps} />;
    case 'checkbox':
      return <input checked={value.value === true || value.value === "1"} {...inpProps} />;
    default:
      return <input {...inpProps} />;
  }
}
