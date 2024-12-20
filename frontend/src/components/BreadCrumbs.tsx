import { useEffect } from 'preact/hooks'
import { navigate } from "wouter-preact/use-browser-location";

import { useBreadcrumbs } from "../hooks/useBreadcrumbs";

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

  const destElt = document.querySelector('header > .breadcrumbs > ol.breadcrumb');
  if (destElt) {
    destElt.innerHTML = payload;
  }

  useEffect(() => {
    for (const crumb of breadcrumbs) {
        document.getElementById(crumb.id)?.addEventListener('click', followInternalLink);
    }
    return () => {
      const anchors = document.querySelectorAll('header > .breadcrumbs .breadcrumb-item > a');
      for (let i=0; i < anchors.length; ++i){
        anchors.item(i).removeEventListener('click', followInternalLink);
      }
    };
  })

  return <div style="display:none" data-location={location} />;
}
