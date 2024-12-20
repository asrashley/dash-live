import { type Signal, useComputed } from "@preact/signals";

import { FormRow, FormRowProps } from "./FormRow.js";
import { Input, InputProps } from "./Input.js";

export interface InputFieldRowProps extends Omit<InputProps, 'title'> {
  data: Signal<object>;
  fullName: string;
  layout: FormRowProps['layout'];
  mode: 'shortName' | 'fullName' | 'cgi';
  name: string;
  prefix?: string;
  shortName: string;
  text: FormRowProps['text'];
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
  const name = mode === 'shortName' ? shortName : mode === 'cgi' ? cgiName: `${prefix}${prefix ? '__': ''}${fullName}`;
  return <FormRow name={name} label={title} text={text} layout={layout} {...props} >
    <Input {...props} name={name} value={value} title={title}/>
    </FormRow>;
}
