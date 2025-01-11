import { useCallback } from "preact/hooks";
import { SelectOptionType } from "../types/SelectOptionType";

interface RadioOptionProps extends SelectOptionType {
  setValue: (name: string, value: string | number) => void;
}

function RadioOption({
  name,
  selected,
  title,
  value,
  disabled,
  setValue,
}: RadioOptionProps) {
  const onClick = useCallback(() => {
    setValue(name, value);
  }, [name, setValue, value]);
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
        checked={selected}
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
  value: string;
}

export function RadioInput({
  name,
  options,
  value,
  setValue,
}: RadioInputProps) {
  return (
    <div>
      {options.map((opt) => (
        <RadioOption
          key={opt.value}
          name={name}
          setValue={setValue}
          selected={value === opt.value}
          {...opt}
        />
      ))}
    </div>
  );
}
