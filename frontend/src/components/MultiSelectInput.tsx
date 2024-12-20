import { type JSX } from "preact";
import { useCallback } from "preact/hooks";
import { SelectOptionType } from "../types/SelectOptionType";
import { SetValueFunc } from "../types/SetValueFunc";

export interface MultiSelectInputProps {
  className: string;
  name: string;
  options: SelectOptionType[];
  setValue: SetValueFunc;
}

export function MultiSelectInput({ className, options, name: fieldName, setValue }: MultiSelectInputProps) {
  const onClick = useCallback((ev: JSX.TargetedEvent<HTMLInputElement>) => {
    const { name, checked } = ev.target as HTMLInputElement;
    setValue(name, checked);
  }, [setValue]);

  const testId = `msi-${fieldName}`;
  return <div data-testid={testId} className={className}>
    {options.map(
      ({ name, title, checked }) => <div
        className="form-check form-check-inline" key={name}
      >
        <input
          name={name}
          className="form-check-input"
          type="checkbox"
          id={`msi${name}`}
          checked={checked}
          onClick={onClick}
        />
        <label className="form-check-label me-3" for={`msi${name}`}>{title}</label>
      </div>
    )}
  </div>;
}
