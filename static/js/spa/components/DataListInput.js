import { html } from "htm/preact";

export function DataListInput({ className="", name, options, ...props }) {
  return html`<input
      className="${className}"
      name="${name}"
      list="list-${name}"
      ...${props}
    />
    <datalist id="list-${name}">
      ${options.map(
        (opt) =>
          html`<option value=${opt.value} selected=${opt.selected}>
            ${opt.title}
          </option>`
      )}
    </datalist>`;
}
