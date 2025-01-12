import { type ReadonlySignal, useComputed } from '@preact/signals';

import { DataListInput } from './DataListInput';
import { MultiSelectInput } from './MultiSelectInput';
import { RadioInput } from './RadioInput';
import { SelectInput } from './SelectInput';
import type { SetValueFunc } from '../types/SetValueFunc';
import type { InputFormData } from '../types/InputFormData';
import type { FormInputItem } from '../types/FormInputItem';
import type { FormRowMode } from '../types/FormRowMode';
import { FormGroupsProps } from '../types/FormGroupsProps';

export interface InputProps extends FormInputItem {
  data: FormGroupsProps['data'];
  disabledFields: FormGroupsProps['disabledFields'];
  mode: FormRowMode;
  validation?: "was-validated" | "has-validation" | "needs-validation";
  setValue: SetValueFunc;
}

type BaseInputProps = {
  name: string;
  id: string;
  type: FormInputItem["type"];
  className: string;
  title: string;
  "aria-describedby": string;
  disabled: ReadonlySignal<boolean>;
  onInput: (ev: Event) => void;
};

interface GetNameProps {
  cgiName: string;
  mode: FormRowMode;
  shortName: string;
  fullName: string;
  prefix?: string;
}

function getName({ cgiName, mode, shortName, fullName, prefix }: GetNameProps): string {
  switch(mode) {
    case 'cgi':
      return cgiName;
    case 'shortName':
      return shortName;
    case 'fullName':
      if (prefix) {
        return `${prefix}__${fullName}`;
      }
      return fullName;
  }
}

export function Input({
  className = "",
  datalist_type,
  type,
  name: cgiName,
  shortName,
  fullName,
  prefix,
  mode,
  data,
  disabledFields,
  setValue,
  error,
  validation,
  title,
  options,
}: InputProps) {
  const name = getName({mode, shortName, cgiName, fullName, prefix});
  const value = useComputed<string | number | undefined>(() => {
      if (!data.value) {
        return undefined;
      }
      const val = (mode === 'fullName' && prefix) ? data.value[prefix][fullName] : data.value[name];
      if (typeof val === "boolean") {
        return val ? "1": "0";
      }
      return val;
  });
  const prefixData = useComputed<InputFormData>(() => (mode === 'fullName' && prefix) ? (data.value[prefix] as InputFormData): data.value);
  const stringValue = useComputed<string>(() => value.value === undefined ? "" : typeof value.value === "string" ? value.value : `${value.value}`);
  const disabled = useComputed<boolean>(() => !!disabledFields[name]);
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
    title,
    disabled,
    className: `${inputClass}${validationClass} ${className}`,
    id: `model-${name}`,
    "aria-describedby": `field-${name}`,
    onInput: (ev: Event) => {
      const target = ev.target as HTMLInputElement;
      setValue(name, target.type === "checkbox" ? target.checked : target.value);
    },
  };
  switch (type) {
    case "radio":
      return <RadioInput setValue={setValue} value={stringValue} options={options} disabledFields={disabledFields} {...inpProps} />;
    case "select":
      return <SelectInput setValue={setValue} value={stringValue} options={options} {...inpProps} />;
    case "multiselect":
      return <MultiSelectInput setValue={setValue} data={prefixData} options={options} {...inpProps} />;
    case "datalist":
      inpProps.type = datalist_type ?? 'text';
      return <DataListInput options={options} value={stringValue} {...inpProps} />;
    case 'checkbox':
      return <input checked={value.value === "1"} {...inpProps} />;
    default:
      return <input {...inpProps} />;
  }
}
