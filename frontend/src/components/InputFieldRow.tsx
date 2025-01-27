import { FormRow, FormRowProps } from "./FormRow";
import { Input, InputProps } from "./Input";
import { FormGroupsProps } from "../types/FormGroupsProps";

export interface InputFieldRowProps extends Omit<InputProps, "title"> {
  layout?: FormRowProps["layout"];
  text?: FormRowProps["text"];
  data: FormGroupsProps['data'];
  disabledFields: FormGroupsProps['disabledFields'];
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
  const name: string =
    mode === "shortName"
      ? shortName
      : mode === "cgi"
      ? cgiName
      : `${prefix}${prefix ? "__" : ""}${fullName}`;
  const describedBy = text ? `text-${name}`: `label-${name}`;
  return (
    <FormRow name={name} label={title} text={text} layout={layout} {...props}>
      <Input
        {...props}
        name={name}
        mode={mode}
        data={data}
        describedBy={describedBy}
        title={title}
        prefix={prefix}
        shortName={shortName}
        fullName={fullName}
      />
    </FormRow>
  );
}
