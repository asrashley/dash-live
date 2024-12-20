import { html } from "htm/preact";

export function SelectOption({value, selected, title}) {
    return html`<option value="${ value }" selected=${selected}>${ title }</option>`;
}

