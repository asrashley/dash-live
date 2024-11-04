import { html } from 'htm/preact';

import { EditStreamCard } from './EditStreamCard.js';

export function AddOrEditStreamPage({name, newStream}) {
  return html`<div>
  <${EditStreamCard} name=${name} newStream=${newStream} />
  </div>`;
}
