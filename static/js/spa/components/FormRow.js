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

function FormText({text}) {
  if (!text) {
    return null;
  }
  return html`<div class="col-3 form-text">${text}</div>`;
}

function ErrorFeedback({error}) {
  if (!error) {
    return null;
  }
  return html`<div class="invalid-feedback" style="display:block">${error}</div>`;
}

export function FormRow({ className = "", name, label, text, type, children, error, options }) {
  return html`
    <div class="row mb-3 form-group ${className}">
      <label class="col-2 col-form-label" htmlFor="field-${name}">${label}:</label>
      <div class="${text ? "col-7" : "col-10"}">${children}</div>
      <${FormText} text=${text} />
      <${ErrorFeedback} error=${error} />
      <${DataList} type=${type} name=${name} options=${options} />
    </div>`;
}
