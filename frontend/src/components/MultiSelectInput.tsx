import { type JSX } from "preact";
import { type ReadonlySignal } from "@preact/signals";
import { useCallback } from "preact/hooks";

import type { SelectOptionType } from "../types/SelectOptionType";
import type { SetValueFunc } from "../types/SetValueFunc";
import type { InputFormData } from '../types/InputFormData';

interface MultiSelectCheckboxProps {
  fieldName: string;
  name?: string;
  title: string;
  data: ReadonlySignal<InputFormData>;
  onClick: (ev: JSX.TargetedEvent<HTMLInputElement>) => void;
}
function MultiSelectCheckbox({ name: optName, fieldName, data, title, onClick }: MultiSelectCheckboxProps) {
  const name = optName ?? fieldName;
  const checked = data.value[name] === "1" || data.value[name] === true;
  return <div
        className="form-check form-check-inline" key={name}
      >
        <input
          name={name}
          className="form-check-input"
          type="checkbox"
          id={`msi${name}`}
          checked={checked}
          onClick={onClick}
        />
        <label className="form-check-label me-3" for={`msi${name}`}>{title}</label>
      </div>;
}
export interface MultiSelectInputProps {
  className: string;
  name: string;
  options: SelectOptionType[];
  data: ReadonlySignal<InputFormData>;
  setValue: SetValueFunc;
}

export function MultiSelectInput({ className, options, data, name: fieldName, setValue }: MultiSelectInputProps) {
  const onClick = useCallback((ev: JSX.TargetedEvent<HTMLInputElement>) => {
    const { name, checked } = ev.target as HTMLInputElement;
    setValue(name, checked);
  }, [setValue]);

  const testId = `msi-${fieldName}`;
  return <div data-testid={testId} className={className}>
    {options.map((opt) => <MultiSelectCheckbox key={opt.name ?? fieldName} fieldName={fieldName} data={data} onClick={onClick} {...opt} />)}
  </div>;
}
