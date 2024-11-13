import { html } from "htm/preact";
import { useComputed } from "@preact/signals";
import { useCallback, useState } from 'preact/hooks';

import { FormRow } from "./FormRow.js";
import { Input } from "./Input.js";

function InputFieldRow({ name, title, data, text, value: defaultValue, ...props }) {
  const fieldValue = useComputed(() => {
    const item = data.value[name] ?? {};
    const { checked = false, value = defaultValue} = item;
    if (props.type === 'checkbox') {
      return checked || !!value;
    }
    return value;
  });

  return html`<${FormRow} name="${name}" label="${title}" text="${text}"  ...${props}>
    <${Input} name="${name}" value=${fieldValue.value} title=${title} ...${props}
  /><//>`;
}

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

function AccordionCollapse({ index, fields, data, expanded }) {
  const className = `accordion-collapse collapse p-3${expanded ? " show" : ""}`;
  return html`<div class="${className}" id="model-group-${index}">
    ${fields.map(
      (field) => html`<${InputFieldRow} data=${data} ...${field}></${InputFieldRow}>`
    )}
  </div>`;
}

export function AccordionItem({ item, index, data, expand }) {
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
    <${AccordionCollapse} ...${item} index=${index} data=${data} expanded=${expanded} />
  </div>`;
}

export function AccordionFormGroup({ groups, data, expand }) {
  const dataWithDefault = useComputed(() => data?.value ?? {})
  return html`<div class="accordion mb-4">
    ${groups.map(
      (grp, idx) =>
        html`<${AccordionItem} item=${grp} index=${idx} data=${dataWithDefault} expand=${expand} />`
    )}
  </div>`;
}
