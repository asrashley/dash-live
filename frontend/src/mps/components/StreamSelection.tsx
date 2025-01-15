import { useCallback, useContext } from "preact/hooks";

import { AllStreamsContext } from '../../hooks/useAllStreams';
import { DecoratedStream } from "../../types/DecoratedStream";

export interface StreamSelectionProps {
  value?: DecoratedStream,
  onChange: (props: {name: string, value: number}) => void;
  name: string;
  error?: string;
  required?: boolean;
}

export function StreamSelection({ value, onChange, name, error, required }: StreamSelectionProps) {
  const { allStreams } = useContext(AllStreamsContext);
  const validationClass = error
    ? " is-invalid"
    : value
    ? " is-valid"
    : "";
  const className = `form-select${validationClass}`;

  const changeHandler = useCallback(
    (ev) => {
      onChange({
        name,
        value: parseInt(ev.target.value, 10),
      });
    },
    [onChange, name]
  );

  return <select
    className={className}
    value={value?.pk}
    name={name}
    onChange={changeHandler}
    required={required}
  >
    <option value="">--Select a stream--</option>
    {allStreams.value.map((s) => <option key={s.pk} value={s.pk}>{s.title}</option>)}
  </select>;
}

