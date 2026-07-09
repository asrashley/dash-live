import { useComputed, type ReadonlySignal } from "@preact/signals";
import { useCallback, useContext } from "preact/hooks";

import { AllStreamsContext } from '../../hooks/useAllStreams';
import { DecoratedStream } from "../../types/DecoratedStream";

export interface StreamSelectionProps {
  value: ReadonlySignal<DecoratedStream| undefined>,
  name: string;
  error?: ReadonlySignal<string| undefined>;
  required?: boolean;
  onChange: (props: {name: string, value: number}) => void;
}

export function StreamSelection({ value, onChange, name, error, required }: StreamSelectionProps) {
  const { allStreams } = useContext(AllStreamsContext);
  const className = useComputed<string>(() => {
    const validationClass = error?.value
      ? " is-invalid"
      : value.value
      ? " is-valid"
    : "";
    return `form-select${validationClass}`;
  });
  const selectValue = useComputed(() => value.value?.pk ?? "");

  const changeHandler = useCallback(
    (ev: Event) => {
      const value = parseInt((ev.target as HTMLSelectElement).value, 10);
      if (!isNaN(value)) {
        onChange({
          name,
          value,
        });
      }
    },
    [onChange, name]
  );

  return <select
    className={className}
    value={selectValue}
    name={name}
    onChange={changeHandler}
    required={required}
  >
    <option value="">--Select a stream--</option>
    {allStreams.value.map((s) => <option key={s.pk} value={s.pk}>{s.title}</option>)}
  </select>;
}

