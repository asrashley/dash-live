import { html } from 'htm/preact';

export function LoadingSpinner() {
    return html`<div className="lds-ring">
    <div className="lds-seg" />
    <div className="lds-seg" />
    <div className="lds-seg" />
    <div className="lds-seg" />
    </div>`;
}

