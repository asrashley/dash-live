import { useComputed, type ReadonlySignal } from "@preact/signals";
import { useCallback } from "preact/hooks";

import { SelectOptionType } from "../types/SelectOptionType";
import { FormGroupsProps } from "../types/FormGroupsProps";

interface RadioOptionProps extends SelectOptionType {
  setValue: (name: string, value: string | number) => void;
  currentValue: ReadonlySignal<string>;
  disabledFields: FormGroupsProps['disabledFields'];
}

function RadioOption({
  name,
  title,
  value,
  currentValue,
  disabledFields,
  setValue,
}: RadioOptionProps) {
  const onClick = useCallback(() => {
    setValue(name, value);
  }, [name, setValue, value]);
  const checked = useComputed<boolean>(() => value === currentValue.value);
  const disabled = useComputed<boolean>(() => !!disabledFields.value[`${name}__${value}`]);
  const id = `radio-${name}-${value}`;

  return (
    <div class="form-check">
      <input
        class="form-check-input"
        type="radio"
        name={name}
        id={id}
        onClick={onClick}
        value={value}
        checked={checked}
        disabled={disabled}
      />
      <label class="form-check-label" for={id}>
        {title}
      </label>
    </div>
  );
}

export interface RadioInputProps {
  name: string;
  options: SelectOptionType[];
  setValue: RadioOptionProps["setValue"];
  value: ReadonlySignal<string>;
  disabledFields: FormGroupsProps['disabledFields'];
}

export function RadioInput({
  name,
  options,
  value,
  disabledFields,
  setValue,
}: RadioInputProps) {
  return (
    <div>
      {options.map((opt) => (
        <RadioOption
          key={opt.value}
          name={name}
          disabledFields={disabledFields}
          setValue={setValue}
          currentValue={value}
          {...opt}
        />
      ))}
    </div>
  );
}
