import { html } from 'htm/preact';
import { useParams } from "wouter-preact";

import { AddOrEditStreamPage } from './AddOrEditStreamPage.js';

export function EditStreamPage() {
  const {name} = useParams();
  return html`<${AddOrEditStreamPage} name="${name}" />`;
}
