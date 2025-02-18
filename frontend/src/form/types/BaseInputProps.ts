import type { ReadonlySignal } from "@preact/signals";
import { StaticInputProps } from "./StaticInputProps";

export type BaseInputProps = {
  name: string;
  id: string;
  type: StaticInputProps["type"];
  className: string | ReadonlySignal<string>;
  title: string;
  placeholder?: string;
  "aria-describedby": string;
  disabled: ReadonlySignal<boolean>;
  onInput: (ev: Event) => void;
};

