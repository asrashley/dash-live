import { html } from "htm/preact";
import { useCallback, useState } from 'preact/hooks';

import { InputFieldRow } from "./InputFieldRow.js";

function AccordionHeader({ expanded, index, title, onClick }) {
  const className = `accordion-button${ expanded ? '': ' collapsed'}`;

  return html`<div class="accordion-header">
    <button
      class="${className}"
      type="button"
      onClick=${onClick}
      aria-expanded="${expanded}"
      aria-controls="model-group-${index}"
    >
      ${title}
    </button>
  </div> `;
}

function AccordionCollapse({ index, fields, expanded, ...props }) {
  const className = `accordion-collapse collapse p-3${expanded ? " show" : ""}`;
  return html`<div class="${className}" id="model-group-${index}">
    ${fields.map(
      (field) => html`<${InputFieldRow} ...${props} ...${field} />`
    )}
  </div>`;
}

export function AccordionItem({ item, index, expand, ...props }) {
  const name = item?.name ?? `${index}`;
  const [expanded, setExpanded] = useState(name === expand);

  const toggle = useCallback(() => {
    setExpanded(!expanded);
  },[expanded]);

  return html`<div
    class="accordion-item ${item.className}"
    id="group-${name}"
    data-name="${name}"
  >
    <${AccordionHeader} title="${item.title}" index=${index} expanded=${expanded} onClick=${toggle} />
    <${AccordionCollapse} index=${index} expanded=${expanded} ...${props} ...${item} />
  </div>`;
}

export function AccordionFormGroup({ groups, ...props }) {
  return html`<div class="accordion mb-4">
    ${groups.map(
      (grp, idx) =>
        html`<${AccordionItem} item=${grp} index=${idx} ...${props} />`
    )}
  </div>`;
}
