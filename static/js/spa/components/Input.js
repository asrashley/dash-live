import { html } from "htm/preact";

import { DataListInput } from './DataListInput.js';
import { MultiSelectInput } from './MultiSelectInput.js';
import { RadioInput } from './RadioInput.js';
import { SelectInput } from './SelectInput.js';

export function Input({
  className = "",
  datalist_type,
  type,
  name,
  value,
  setValue,
  error,
  validation,
  title,
  options,
}) {
  const inputClass =
    type === "checkbox"
      ? "form-check-input"
      : type === "select"
      ? "form-select"
      : "form-control";
  const validationClass = error
    ? " is-invalid"
    : validation === "was-validated"
    ? " is-valid"
    : "";
  const inpProps = {
    name,
    type,
    className: `${inputClass}${validationClass} ${className}`,
    title,
    id: `model-${name}`,
    value: value.value,
    "aria-describedby": `field-${name}`,
    onInput: (ev) => {
      const { target } = ev;
      setValue(name, target.type === "checkbox" ? target.checked : target.value);
    },
  };
  if (type === "checkbox") {
    inpProps.checked = value.value === true || value.value === "1";
  }
  switch (type) {
    case "radio":
      return html`<${RadioInput} setValue=${setValue} options=${options} ...${inpProps} />`;
    case "select":
      return html`<${SelectInput} options=${options} ...${inpProps} />`;
    case "multiselect":
      return html`<${MultiSelectInput} setValue=${setValue} options=${options} ...${inpProps} />`;
    case "datalist":
      inpProps.type = datalist_type ?? 'text';
      return html`<${DataListInput} options=${options} ...${inpProps} />`;
    default:
      return html`<input ...${inpProps} />`;
  }
}
