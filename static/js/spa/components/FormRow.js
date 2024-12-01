import { html } from "htm/preact";

import { SelectOption } from "./SelectOption.js";

function DataList({name, options, type='datallist'}) {
  if (type !== 'datalist') {
    return null;
  }
  return html`<datalist id="list-${ name }">
  ${ options.map(opt => html`<${SelectOption} ...${opt} />`)}
</datalist>`;
}

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

export function FormRow({ className = "", name, layout, label, text, type, children, error, options }) {
  let [left, middle, right] = layout ?? [2, 7, 3];
  if (!text) {
    middle += right;
  }
  return html`
    <div class="row mb-3 form-group ${className}">
      <label className="col-${left} col-form-label" htmlFor="field-${name}">${label}:</label>
      <div className="col-${middle}">${children}</div>
      <${FormText} text=${text} className="col-${right}" />
      <${ErrorFeedback} error=${error} />
      <${DataList} type=${type} name=${name} options=${options} />
    </div>`;
}
