import { type Signal, useComputed } from "@preact/signals";

import { FormRow, FormRowProps } from "./FormRow";
import { Input, InputProps } from "./Input";
import { FormRowMode } from "../types/FormRowMode";

export interface InputFieldRowProps
  extends Omit<InputProps, "title" | "value"> {
  data: Signal<object>;
  fullName: string;
  layout?: FormRowProps["layout"];
  mode: FormRowMode;
  name: string;
  shortName: string;
  text?: FormRowProps["text"];
  title: string;
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
  const value = useComputed(() => {
    if (mode === "shortName") {
      return data.value[shortName];
    }
    if (mode === "cgi") {
      return data.value[cgiName];
    }
    if (prefix) {
      return data.value[prefix][fullName];
    }
    return data.value[fullName];
  });
  const name =
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
        value={value}
        title={title}
        prefix={prefix}
        shortName={shortName}
        fullName={fullName}
      />
    </FormRow>
  );
}
