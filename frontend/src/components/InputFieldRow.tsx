import { useComputed, type ReadonlySignal } from "@preact/signals";
import { FormRow, FormRowProps } from "./FormRow";
import { Input } from "./Input";
import { InputProps } from "../types/InputProps";

export interface InputFieldRowProps extends Omit<InputProps, "error"> {
  layout?: FormRowProps["layout"];
  text?: FormRowProps["text"];
  errors?: ReadonlySignal<Record<string, string>>;
}

export function InputFieldRow({
  name: cgiName,
  shortName,
  fullName,
  prefix,
  title,
  data,
  layout,
  mode,
  text,
  errors,
  ...props
}: InputFieldRowProps) {
  const name: string =
    mode === "shortName"
      ? shortName
      : mode === "cgi"
      ? cgiName
      : `${prefix}${prefix ? "__" : ""}${fullName}`;
  const describedBy = text ? `text-${name}`: `label-${name}`;
  const errorSig = useComputed(() => errors?.value[name]);
  const error = errors ? errorSig : undefined;

  return (
    <FormRow name={name} label={title} text={text} layout={layout} error={error} {...props}>
      <Input
        {...props}
        name={name}
        mode={mode}
        data={data}
        describedBy={describedBy}
        error={error}
        title={title}
        prefix={prefix}
        shortName={shortName}
        fullName={fullName}
      />
    </FormRow>
  );
}
