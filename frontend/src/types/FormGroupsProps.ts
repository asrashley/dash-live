import { type Signal } from "@preact/signals";
import { InputFormGroup } from "./InputFormGroup";
import { FormRowMode } from "./FormRowMode";
import { SetValueFunc } from "./SetValueFunc";
import { InputFormData } from "./InputFormData";

export interface FormGroupsProps {
  groups: InputFormGroup[];
  data: Signal<InputFormData>;
  expand?: string;
  mode: FormRowMode;
  layout?: number[];
  setValue: SetValueFunc;
}
