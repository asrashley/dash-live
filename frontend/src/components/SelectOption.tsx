import { SelectOptionType } from "../types/SelectOptionType";

export function SelectOption({ value, selected, title }: SelectOptionType) {
  return (
    <option value={value} selected={selected}>
      {title}
    </option>
  );
}
