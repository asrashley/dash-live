import { type JSX } from 'preact';
import { useCallback } from "preact/hooks";
import { useComputed, type ReadonlySignal } from "@preact/signals";
import { Temporal } from "temporal-polyfill";

function pad(num: number): string {
  return `0${num}`.slice(-2);
}

function isoDurationToValue(duration: string | null | undefined): string {
  if (duration === "" || !duration) {
    return "00:00:00";
  }
  const dur = Temporal.Duration.from(duration);
  const { hours, minutes, seconds } = dur;
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function valueToIsoDuration(value: string): string {
  const digits = value.split(":").map((d) => parseInt(d, 10));
  if (digits.length === 2) {
    const [minutes, seconds] = digits;
    return Temporal.Duration.from({ minutes, seconds }).toString();
  }
  const [hours, minutes, seconds] = digits;
  return Temporal.Duration.from({ hours, minutes, seconds }).toString();
}

export interface TimeDeltaInputProps {
  disabled?: boolean;
  value: ReadonlySignal<string | null | undefined>;
  name: string;
  error?: ReadonlySignal<string | undefined>;
  min?: string;
  required?: boolean;
  step?: string;
  onChange?: (name: string, value: string) => void;
}

export function TimeDeltaInput({
  value,
  name,
  error,
  min = "00:00:00",
  step = "1",
  onChange,
  disabled,
}: TimeDeltaInputProps) {
  const changeHandler = useCallback(
    (ev: JSX.TargetedEvent<HTMLInputElement>) => {
      ev.preventDefault();
      const dur = valueToIsoDuration((ev.target as HTMLInputElement).value);
      onChange?.(name, dur);
    },
    [name, onChange]
  );
  const timeValue = useComputed<string>(() => isoDurationToValue(value.value));
  const className = useComputed<string>(() => `form-control ${
    disabled ? "" : error?.value ? "is-invalid" : "is-valid"
  }`);
  return (
    <input
      type="time"
      className={className}
      value={timeValue}
      name={name}
      step={step}
      min={min}
      onInput={changeHandler}
      disabled={disabled}
    />
  );
}
