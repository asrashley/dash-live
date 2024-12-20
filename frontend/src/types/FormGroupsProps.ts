import { type Signal } from "@preact/signals";
import { InputFormGroup } from "./InputFormGroup";
import { FormRowMode } from "./FormRowMode";
import { SetValueFunc } from "./SetValueFunc";

export interface FormGroupsProps {
  groups: InputFormGroup[];
  data: Signal<object>;
  expand?: string;
  mode: FormRowMode;
  layout?: number[];
  setValue: SetValueFunc;
}
