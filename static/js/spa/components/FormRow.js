import { html } from "htm/preact";

export function FormRow({ className = "", name, label, text, children, error }) {
  const textDiv = text
    ? html`<div class="col-3 form-text">${text}</div>`
    : null;
  const errDiv = error
    ? html`<div class="invalid-feedback">${error}</div>`
    : null;

  return html`
    <div class="row mb-3 form-group ${className}">
      <label class="col-2 col-form-label" htmlFor="field-${name}">
        ${label}:
      </label>
      <div class="${text ? "col-7" : "col-10"}">${children}</div>
      ${textDiv}${errDiv}
    </div>`;
}

