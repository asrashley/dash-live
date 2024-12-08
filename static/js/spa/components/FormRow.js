import { html } from "htm/preact";

function FormText({text, className}) {
  if (!text) {
    return null;
  }
  return html`<div class="${className} form-text">${text}</div>`;
}

function ErrorFeedback({error}) {
  if (!error) {
    return null;
  }
  return html`<div class="invalid-feedback" style="display:block">${error}</div>`;
}

export function FormRow({ className = "", name, layout, label, text, children, error }) {
  let [left, middle, right] = layout ?? [2, 7, 3];
  if (!text) {
    middle += right;
  }
  return html`
    <div class="row mb-2 form-group ${className}">
      <label className="col-${left} col-form-label" htmlFor="field-${name}">${label}:</label>
      <div className="col-${middle}">${children}</div>
      <${FormText} text=${text} className="col-${right}" />
      <${ErrorFeedback} error=${error} />
    </div>`;
}
