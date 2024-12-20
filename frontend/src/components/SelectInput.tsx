import { SelectOption, SelectOptionProps } from "./SelectOption";

export interface SelectInputProps {
  className: string;
  options: SelectOptionProps[];
  value: string | number;
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
        <SelectOption selected={value === opt.value} {...opt} />
      ))}
    </select>
  );
}
