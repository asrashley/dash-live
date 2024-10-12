import { html } from 'htm/preact';

import { AddOrEditStreamPage } from './AddOrEditStreamPage.js';

export function AddStreamPage() {
  return html`<${AddOrEditStreamPage} name=".add" newStream />`;
}
