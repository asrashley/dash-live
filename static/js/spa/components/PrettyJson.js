import { html } from "htm/preact";

function Value({val}) {
    if (typeof val === "string") {
        return html`<span className="value">"${val}"</span>`;
    }
    if (Array.isArray(val)) {
        return html`[${val.map((item) => html`<${Value} val=${item}><//>`)}]`;

    }
    if (typeof val === "object") {
        return html`<${PrettyJson} data=${val} />`;
    }
    const sval = `${val}`;
    return html`<span className="value">${sval}</span>`;
}

function KeyValue({keyName, value, idx}) {
    return html`${idx > 0 ? ', ': ''}<span className="key">${keyName}</span>: <${Value} val=${value} />`;
}

export function PrettyJson({data = {}, className}) {
    return html`<div className=${`json bg-secondary-subtle border border-dark-subtle ${className}`}>{
    ${ Object.entries(data).map(([key, value], idx) =>
        html`<${KeyValue} key=${key} idx=${idx} keyName=${key} value=${value} />`)}
}</div>`;
}
