import { useComputed, type ReadonlySignal } from "@preact/signals";

import { SelectOptionType } from "../types/SelectOptionType";

export interface SelectOptionProps extends SelectOptionType {
  currentValue: ReadonlySignal<string>;
}

export function SelectOption({ currentValue, value, title }: SelectOptionProps) {
  const selected = useComputed<boolean>(() => currentValue.value === value);
  return <option value={value} selected={selected}>{title}</option>;
}
