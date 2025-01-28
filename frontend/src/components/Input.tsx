import { useComputed } from '@preact/signals';

import { DataListInput } from './DataListInput';
import { MultiSelectInput } from './MultiSelectInput';
import { RadioInput } from './RadioInput';
import { SelectInput } from './SelectInput';
import type { InputFormData } from '../types/InputFormData';
import type { FormRowMode } from '../types/FormRowMode';
import { PasswordInput } from './PasswordInput';
import { BaseInputProps } from '../types/BaseInputProps';
import { InputProps } from '../types/InputProps';


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
  allowReveal,
  className = "",
  datalist_type,
  type,
  name: cgiName,
  shortName,
  fullName,
  prefix,
  mode,
  describedBy,
  data,
  disabledFields,
  error,
  setValue,
  title,
  options,
  placeholder
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
  const inputClass = useComputed<string>(() => {
    const formCls = type === "checkbox" ? "form-check-input" : type === "select" ? "form-select" : "form-control";
    const err = error.value ? " is-invalid" : " is-valid";
    return `${formCls}${err} ${className}`;
  });

  const inpProps: BaseInputProps = {
    name,
    type,
    title,
    disabled,
    placeholder,
    className: inputClass,
    id: `model-${name}`,
    "aria-describedby": describedBy,
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
    case 'password':
      return <PasswordInput value={stringValue} allowReveal={allowReveal} {...inpProps} />;
    default:
      return <input value={value} {...inpProps} />;
  }
}
