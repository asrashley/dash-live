import { html } from 'htm/preact';

import { EditStreamCard } from './EditStreamCard.js';

export default function AddStreamPage() {
  return html`<${EditStreamCard} name=".add" newStream />`;
}
