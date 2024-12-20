import { html } from "htm/preact";
import { useCallback, useState } from 'preact/hooks';

import { InputFieldRow } from "./InputFieldRow.js";

function TabLink({activeTab, setActive, disabled, name}) {
    const active = activeTab === name;
    const props = {
        className: `nav-link ${active ? "active" : ""}`,
        href: '#',
        id: `${name}-tab`,
    };
    const onClick = useCallback((ev) => {
        ev.preventDefault();
        setActive(name);
    }, [setActive, name]);

    if (active) {
        props['aria-current'] = 'page';
    }
    if (disabled) {
        props['aria-disabled'] = true;
        props.className += ' disabled';
    }
    return html`<li className="nav-item"><a onClick=${onClick} ...${props}>${name}</a></li>`;
}

function TabContent({activeTab, name, fields, ...props}) {
    const active = activeTab === name;
    const className = `tab-pane fade ${active ? "show active": ""}`;
    const labelledBy = `${name}-tab`
    return html`<div id=${name} className=${className} role="tabpanel" aria-labelledby=${labelledBy}>
      ${fields.map(
        (field) => html`<${InputFieldRow} ...${props} ...${field} />`
      )}
    </div>`;
}

export function TabFormGroup({ groups, ...props }) {
  const [ activeTab, setActiveTab ] = useState(groups[0].name);
  return html`<div>
  <ul className="nav nav-tabs mb-3">
    ${groups.map((grp) => html`<${TabLink} activeTab=${activeTab} setActive=${setActiveTab} ...${props} ...${grp} />`)}
  </ul>
  <div className="tab-content">
    ${groups.map((grp) => html`<${TabContent} activeTab=${activeTab} ...${props} ...${grp} />`)}
  </div>
</div>`;
}
