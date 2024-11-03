import { html } from "htm/preact";
import { useEffect } from 'preact/hooks'
import { useLocation, useRouter } from 'wouter-preact';
import { navigate } from "wouter-preact/use-browser-location";

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

export const useBreadcrumbs = () => {
  const [location, setLocation] = useLocation();
  const { base } = useRouter();

  const baseParts = base === "" ? [""] : base.split('/');
  const parts = location === "/" ? [""] : location.split('/').slice(baseParts.length - 1);

  const breadcrumbs = parts.map((title, idx) => {
    const href = idx === 0 ? `${base}/` : `${base}${parts.slice(0, idx + 1).join('/')}`;
    const active = idx == (parts.length - 1);
    const useLink = idx > 0;
    const id = `crumb_${idx}`;
    if (title === '') {
      title = 'Home';
    }
    return {title, active, href, useLink, id};
  });

  return {breadcrumbs, location, setLocation};
};

export function BreadCrumbs() {
  const { breadcrumbs, location } = useBreadcrumbs();
  const payload = breadcrumbs.map(crumb => breadCrumbItemHtml(crumb)).join('');

  document.querySelector('header > .breadcrumbs > ol.breadcrumb').innerHTML = payload;

  useEffect(() => {
    for (const crumb of breadcrumbs) {
      if (crumb.useLink) {
        document.getElementById(crumb.id)?.addEventListener('click', followInternalLink);
      }
    }
    return () => {
      for (const elt of document.querySelectorAll('header > .breadcrumbs .breadcrumb-item > a')) {
        elt.removeEventListener('click', followInternalLink);
      }
    };
  })

  return html`<div style="display:none" data-location="${location}" />`;
}
