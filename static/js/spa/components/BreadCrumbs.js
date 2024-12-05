import { html } from "htm/preact";
import { useEffect } from 'preact/hooks'
import { navigate } from "wouter-preact/use-browser-location";

import { useBreadcrumbs } from "@dashlive/hooks";

function followInternalLink(ev) {
  const href = ev.target.getAttribute('href');
  ev.preventDefault();
  navigate(href, {replace: true});
  return false;
}

/*
NOTE: this returns an HTML string, *not* markup objects, as it is used to
directly manipulate a DOM element outside of the Preact app.
*/
function breadCrumbItemHtml({title, href, active, id}) {
  let body;

  if (active) {
    body = title;
  } else {
    body = `<a href="${ href }" title="${title}">${ title }</a>`;
  }
  return `<li id="${id}" class="breadcrumb-item ${active ? 'active': ''}">${body}</li>`;
}
export function BreadCrumbs() {
  const { breadcrumbs, location } = useBreadcrumbs();
  const payload = breadcrumbs.map(crumb => breadCrumbItemHtml(crumb)).join('');

  document.querySelector('header > .breadcrumbs > ol.breadcrumb').innerHTML = payload;

  useEffect(() => {
    for (const crumb of breadcrumbs) {
        document.getElementById(crumb.id)?.addEventListener('click', followInternalLink);
    }
    return () => {
      for (const elt of document.querySelectorAll('header > .breadcrumbs .breadcrumb-item > a')) {
        elt.removeEventListener('click', followInternalLink);
      }
    };
  })

  return html`<div style="display:none" data-location="${location}" />`;
}
