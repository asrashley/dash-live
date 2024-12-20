import { useCallback } from "preact/hooks";
import { MultiSelectOptionType } from "../types/SelectOptionType";

export interface MultiSelectInputProps {
  className: string;
  name: string;
  options: MultiSelectOptionType[];
  setValue: (name: string, value: string | number) => void;
}

export function MultiSelectInput({ className, options, name: fieldName, setValue }: MultiSelectInputProps) {
  const onClick = useCallback((ev) => {
    const { name, checked } = ev.target;
    setValue(name, checked);
  }, [setValue]);

  const testId = `msi-${fieldName}`;
  return <div data-testid={testId} className={className}>
    {options.map(
      ({ name, title, checked }) => <div
        className="form-check form-check-inline"
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
