import { html } from "htm/preact";

import { FormRow } from './FormRow.js';
import { TextInput } from './TextInput.js';

export function TextInputRow({ name, label, text, error, ...props}) {
  return html`
<${FormRow} name=${name} label=${label} text=${text} error=${error} >
  <${TextInput} name="${name}" ...${props} />
</${FormRow}>`;
}
