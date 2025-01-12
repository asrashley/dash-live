import { type ReadonlySignal } from "@preact/signals";
import { InputFormGroup } from "./InputFormGroup";
import { FormRowMode } from "./FormRowMode";
import { SetValueFunc } from "./SetValueFunc";
import { InputFormData } from "./InputFormData";

export interface FormGroupsProps {
  groups: InputFormGroup[];
  data: ReadonlySignal<InputFormData>;
  disabledFields: ReadonlySignal<Record<string, boolean>>;
  expand?: string;
  mode: FormRowMode;
  layout?: number[];
  setValue: SetValueFunc;
}
