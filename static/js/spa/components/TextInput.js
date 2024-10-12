import { html } from 'htm/preact';

export function TextInput({name, error, value, onInput, required}) {
  const className = `form-control ${error ? "is-invalid" : "is-valid"}`;
  return html`
    <input class="${className}" id="field-${name}" name="${name}"
      type="text" value=${value} onInput=${onInput}
      required=${required} />`;
}
