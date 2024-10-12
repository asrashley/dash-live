import { html } from 'htm/preact';

export function CheckBox({checked, name, label, onClick, children = null}) {
  return html`
<input class="form-check-input col-2" type="checkbox" id="check_${name}" name="${name}" checked=${checked} onClick=${onClick} />
<label class="form-check-label col-6" for="check_${name}">${label}</label>
${ children }
`;
}
