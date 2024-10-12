import { html } from 'htm/preact';
import { useCallback, useMemo } from 'preact/hooks';
import { Temporal } from 'temporal-polyfill';

function pad(num) {
  return `0${num}`.slice(-2);
}

function isoDurationToValue(duration) {
  if (duration === '' || duration === null) {
    return '00:00:00';
  }
  const dur = Temporal.Duration.from(duration);
  const { hours, minutes, seconds } = dur;
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function valueToIsoDuration(value) {
  const digits = value.split(':').map(d => parseInt(d, 10));
  if (digits.length === 2) {
    const [minutes, seconds] = digits;
    return Temporal.Duration.from({minutes, seconds}).toString();
  }
  const [hours, minutes, seconds] = digits;
  return Temporal.Duration.from({hours, minutes, seconds}).toString();
}

export function TimeDeltaInput({value, name, error, min="00:00:00", onChange}) {
  const changeHandler = useCallback((ev) => {
    const dur = valueToIsoDuration(ev.target.value);
    onChange({
      name,
      value: dur,
      target: {
        name,
        value: dur
      }
    });
  }, [name, onChange]);
  const timeValue = useMemo(() => isoDurationToValue(value), [value]);
  const className = `form-control ${error ? "is-invalid" : "is-valid"}`;
  return html`<input type="time" class="${className}" value=${timeValue} 
    name=${name} step="1" min="${min}" onInput=${changeHandler} />`;
}
