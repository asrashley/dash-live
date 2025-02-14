import { type ReadonlySignal } from "@preact/signals";
import { SelectOptionType } from "../types/SelectOptionType";
import { SetValueFunc } from "../types/SetValueFunc";
import { SelectOption } from "./SelectOption";

export interface SelectInputProps {
  className: string | ReadonlySignal<string>;
  options: SelectOptionType[];
  value: ReadonlySignal<string>;
  disabled: ReadonlySignal<boolean>;
  setValue: SetValueFunc;
}

export function SelectInput({
  className,
  options,
  value,
  disabled,
  ...props
}: SelectInputProps) {
  return (
    <select className={className} value={value} disabled={disabled} {...props}>
      {options.map((opt) => (
        <SelectOption key={opt.value} currentValue={value} {...opt} />
      ))}
    </select>
  );
}
