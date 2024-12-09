import { html } from 'htm/preact';
import { useParams } from "wouter-preact";

import { EditStreamCard } from './EditStreamCard.js';

export default function EditStreamPage() {
  const {mps_name} = useParams();
  return html`<${EditStreamCard} name="${mps_name}" />`;
}
