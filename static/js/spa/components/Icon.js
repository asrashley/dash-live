import { html } from 'htm/preact';

export function Icon({name, className=""}) {
  return html`<span class="bi icon bi-${name} ${className}" role="icon"></span>`;
}

function doNothing(ev) {
  ev.preventDefault();
  return false;
}

export function IconButton({name, onClick, disabled, className=""}) {
  if (disabled) {
    return html`<a onClick=${doNothing} class="disabled ${className}"><${Icon} name="${name}" /></a>`;
  }
  return html`<a onClick=${onClick} class="${className}" href="#"><${Icon} name="${name}" /></a>`;
}
