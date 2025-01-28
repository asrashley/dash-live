import { type ReadonlySignal } from "@preact/signals";
import { StaticInputProps } from "./StaticInputProps";
import { FormRowMode } from "./FormRowMode";
import { SetValueFunc } from "./SetValueFunc";
import { InputFormData } from "./InputFormData";

export interface InputProps extends StaticInputProps {
  data: ReadonlySignal<InputFormData>;
  disabledFields?: ReadonlySignal<Record<string, boolean>>;
  //errors?: ReadonlySignal<Record<string, string>>;
  error: ReadonlySignal<string|undefined>;
  mode: FormRowMode;
  //validation?: "was-validated" | "has-validation" | "needs-validation";
  describedBy?: string;
  setValue: SetValueFunc;
}
