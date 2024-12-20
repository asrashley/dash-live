import { SelectOptionType } from "../types/SelectOptionType";
import { SetValueFunc } from "../types/SetValueFunc";
import { SelectOption } from "./SelectOption";

export interface SelectInputProps {
  className: string;
  options: SelectOptionType[];
  value: string | number;
  setValue: SetValueFunc;
}

export function SelectInput({
  className,
  options,
  value,
  ...props
}: SelectInputProps) {
  return (
    <select className={className} value={value} {...props}>
      {options.map((opt) => (
        <SelectOption key={opt.value} selected={value === opt.value} {...opt} />
      ))}
    </select>
  );
}
