import { type ReadonlySignal } from "@preact/signals";
import { InputFormData } from "../types/InputFormData";
import { FormRow, FormRowProps } from "./FormRow";
import { Input, InputProps } from "./Input";

export interface InputFieldRowProps
  extends Omit<InputProps, "title"> {
  layout?: FormRowProps["layout"];
  text?: FormRowProps["text"];
  title: string;
  data: ReadonlySignal<InputFormData>;
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
  ...props
}: InputFieldRowProps) {
  const name: string =
    mode === "shortName"
      ? shortName
      : mode === "cgi"
      ? cgiName
      : `${prefix}${prefix ? "__" : ""}${fullName}`;
  return (
    <FormRow name={name} label={title} text={text} layout={layout} {...props}>
      <Input
        {...props}
        name={name}
        mode={mode}
        data={data}
        title={title}
        prefix={prefix}
        shortName={shortName}
        fullName={fullName}
      />
    </FormRow>
  );
}
