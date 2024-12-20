import { type JSX } from "preact";

export interface TextInputProps extends Omit<JSX.InputHTMLAttributes<HTMLInputElement>, 'name'> {
  name: string;
  error?: string;
}

export function TextInput({name, error, ...props}: TextInputProps) {
  const className = `form-control ${error ? "is-invalid" : "is-valid"}`;

  return <input className={className} id={`field-${name}`} name={name}
      type="text" {...props} />;
}
