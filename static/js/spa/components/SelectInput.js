import { html } from "htm/preact";

import { SelectOption } from "./SelectOption.js";

export function SelectInput({ className, options, value, ...props }) {
  return html`<select className="${className}" value=${value} ...${props}>
    ${options.map(
      (opt) =>
        html`<${SelectOption} selected=${value === opt.value} ...${opt} />`
    )}
  </select>`;
}
