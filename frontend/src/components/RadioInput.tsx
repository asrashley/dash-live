import { useCallback } from "preact/hooks";
import { SelectOptionType } from "../types/SelectOptionType";

interface RadioOptionProps extends SelectOptionType {
  setValue: (name: string, value: string | number) => void;
}

function RadioOption({ name, selected, title, value, disabled, setValue }: RadioOptionProps) {
  const onClick = useCallback(() => {
    setValue(name, value);
  }, [name, setValue, value]);
  return <div class="form-check">
    <input
      class="form-check-input"
      type="radio"
      name={name}
      id={`radio-${name}-${value}`}
      onClick={onClick}
      value={value}
      checked={selected}
      disabled={disabled}
    />
    <label class="form-check-label" for={`radio-${name}-${value}`}>{title}</label>
  </div>;
}

export interface RadioInputProps {
  options: SelectOptionType[];
  setValue: RadioOptionProps['setValue'];
}

export function RadioInput({ options, setValue }) {
  return <div>
    {options.map(
      (opt) => <RadioOption key={opt.value} setValue={setValue} {...opt} />
    )}
  </div>;
}
