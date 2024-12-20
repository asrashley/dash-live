import { FormRow, FormRowProps } from "./FormRow";
import { TextInput, TextInputProps } from "./TextInput";

export type TextInputRowProps = Pick<FormRowProps, "name" | "label" | "text" | "error"> & TextInputProps;

export function TextInputRow({
  name,
  label,
  text,
  error,
  ...props
}: TextInputRowProps) {
  return (
    <FormRow name={name} label={label} text={text} error={error}>
      <TextInput name={name} error={error} {...props} />
    </FormRow>
  );
}
