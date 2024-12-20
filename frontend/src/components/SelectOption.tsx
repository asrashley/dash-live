export interface SelectOptionProps {
  value: string | number;
  selected: boolean;
  title: string;
}
export function SelectOption({ value, selected, title }: SelectOptionProps) {
  return (
    <option value={value} selected={selected}>
      {title}
    </option>
  );
}
