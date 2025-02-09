import { type JSX } from "preact";
import { useComputed, type ReadonlySignal } from "@preact/signals";
import { useCallback } from "preact/hooks";

import type { SelectOptionType } from "../types/SelectOptionType";
import type { SetValueFunc } from "../types/SetValueFunc";
import type { InputFormData } from "../types/InputFormData";
import { InputProps } from "../types/InputProps";

interface MultiSelectCheckboxProps {
  name: string;
  title: string;
  data: ReadonlySignal<InputFormData>;
  disabledFields: InputProps["disabledFields"];
  onClick: (ev: JSX.TargetedEvent<HTMLInputElement>) => void;
}

function MultiSelectCheckbox({
  name,
  data,
  disabledFields,
  title,
  onClick,
}: MultiSelectCheckboxProps) {
  const checked = useComputed<boolean>(() => data.value[name] === "1" || data.value[name] === true);
  const disabled = useComputed<boolean>(() => !!disabledFields.value[name]);

  return (
    <div className="form-check form-check-inline" key={name}>
      <input
        name={name}
        className="form-check-input"
        type="checkbox"
        id={`msi${name}`}
        checked={checked}
        disabled={disabled}
        onClick={onClick}
      />
      <label className="form-check-label me-3" for={`msi${name}`}>
        {title}
      </label>
    </div>
  );
}
export interface MultiSelectInputProps {
  className: string | ReadonlySignal<string>;
  name: string;
  options: SelectOptionType[];
  data: ReadonlySignal<InputFormData>;
  disabledFields: InputProps["disabledFields"];
  setValue: SetValueFunc;
}

export function MultiSelectInput({
  className,
  options,
  name: fieldName,
  setValue,
  ...props
}: MultiSelectInputProps) {
  const onClick = useCallback(
    (ev: JSX.TargetedEvent<HTMLInputElement>) => {
      const { name, checked } = ev.target as HTMLInputElement;
      setValue(name, checked);
    },
    [setValue]
  );

  const testId = `msi-${fieldName}`;
  return (
    <div data-testid={testId} className={className}>
      {options.map(({name, ...opt}) => (
        <MultiSelectCheckbox
          key={name ?? fieldName}
          name={name ?? fieldName}
          onClick={onClick}
          {...props}
          {...opt}
        />
      ))}
    </div>
  );
}
