import { FormRow, FormRowProps } from "./FormRow.js";
import { TextInput, TextInputProps } from "./TextInput.js";

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
      <TextInput name="${name}" error={error} {...props} />
    </FormRow>
  );
}
