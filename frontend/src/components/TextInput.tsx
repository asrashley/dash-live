import { type JSX } from "preact";
import { useComputed, type ReadonlySignal } from "@preact/signals";

export interface TextInputProps extends Omit<JSX.InputHTMLAttributes<HTMLInputElement>, 'name'> {
  name: string;
  error?: ReadonlySignal<string>;
}

export function TextInput({name, error, ...props}: TextInputProps) {
  const className = useComputed(() => `form-control${error ? (error.value ? " is-invalid" : " is-valid") : ""}`);

  return <input className={className} id={`field-${name}`} name={name}
      type="text" {...props} />;
}
