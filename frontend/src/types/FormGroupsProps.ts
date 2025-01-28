import { InputFormGroup } from "./InputFormGroup";
import { FormRowMode } from "./FormRowMode";
import { SetValueFunc } from "./SetValueFunc";
import { InputProps } from "./InputProps";

export interface FormGroupsProps extends Pick<InputProps, "data" | "disabledFields"> {
  groups: InputFormGroup[];
  expand?: string;
  mode: FormRowMode;
  layout?: number[];
  setValue: SetValueFunc;
}
