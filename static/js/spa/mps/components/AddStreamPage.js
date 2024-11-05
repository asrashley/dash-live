import { html } from 'htm/preact';

import { EditStreamCard } from './EditStreamCard.js';

export function AddStreamPage() {
  return html`<${EditStreamCard} name=".add" newStream />`;
}
