import { html } from 'htm/preact';
import { useCallback, useState } from 'preact/hooks';

function DropDownItem({href = "#", onClick, setExpanded, children}) {
    const click = useCallback((ev) => {
        ev.preventDefault();
        setExpanded(false);
        onClick(ev);
    }, [onClick, setExpanded]);
  return html`<li>
    <a class="dropdown-item" href="${href}" onClick=${click}>${children}</a>
    </li>`;
}

export function DropDownMenu({children, menu, linkClass="btn btn-secondary"}) {
    const [expanded, setExpanded] = useState(false);

    const toggleMenu = (ev) => {
        ev.preventDefault();
        setExpanded(!expanded);
    };

    const show = expanded ? 'show': '';

    return html`<div class="dropdown">
  <a class="${linkClass} dropdown-toggle ${show}" href="#" onClick=${toggleMenu}
    role="button" aria-expanded=${expanded}>
    ${children}
  </a>
  <ul class="dropdown-menu ${show}">
  ${menu.map(item => html`
    <${DropDownItem} onClick=${item.onClick} setExpanded=${setExpanded} href="${item.href}">${item.title}<//>`)}
  </ul>
</div>`;
}