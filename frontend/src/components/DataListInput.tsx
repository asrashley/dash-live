import { Fragment, type JSX } from "preact";
import { useComputed, type ReadonlySignal } from "@preact/signals";
import { SelectOptionType } from "../types/SelectOptionType";

interface DataListOptionProps {
  currentValue: ReadonlySignal<string>;
  value: string;
  title: string;
}
function DataListOption({value, title, currentValue}: DataListOptionProps) {
  const selected = useComputed<boolean>(() => currentValue.value === value);

  return <option value={value} selected={selected}>{title}</option>;
}
export interface DataListInputProps extends Omit<JSX.InputHTMLAttributes<HTMLInputElement>, 'value'> {
  name: string;
  options: SelectOptionType[];
  className?: string | ReadonlySignal<string>;
  value: ReadonlySignal<string>;
}

export function DataListInput({ className = "", name, options, value, ...props }: DataListInputProps) {
  const dataListId = `list-${name}`;
  return (
    <Fragment>
      <input
        className={className}
        name={name}
        list={dataListId}
        {...props}
      />
      <datalist id={dataListId}>
        {options.map((opt) => <DataListOption key={opt.value} currentValue={value} {...opt} />)}
      </datalist>
    </Fragment>
  );
}
