import { html } from "htm/preact";

export function CheckBox({
  name,
  label,
  inputClass = "col-2",
  labelClass = "col-6",
  children = null,
  ...props
}) {
  return html`
    <input
      class=${`form-check-input ${inputClass}`}
      type="checkbox"
      id="check_${name}"
      name="${name}"
      ...${props}
    />
    <label class=${`form-check-label ${labelClass}`} for="check_${name}"
      >${label}</label
    >
    ${children}
  `;
}
