import { type ReadonlySignal } from "@preact/signals";
import { StaticInputProps } from "./StaticInputProps";
import { FormRowMode } from "./FormRowMode";
import { SetValueFunc } from "./SetValueFunc";
import { InputFormData } from "./InputFormData";

export interface InputProps extends StaticInputProps {
  data: ReadonlySignal<InputFormData>;
  disabledFields?: ReadonlySignal<Record<string, boolean>>;
  error: ReadonlySignal<string|undefined>;
  mode?: FormRowMode;
  describedBy?: string;
  setValue: SetValueFunc;
}
