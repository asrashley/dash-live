import { html } from 'htm/preact';

export function CheckBox({name, label, children = null, ...props}) {
  return html`
<input class="form-check-input col-2" type="checkbox" id="check_${name}"
  name="${name}" ...${props} />
<label class="form-check-label col-6" for="check_${name}">${label}</label>
${ children }
`;
}
