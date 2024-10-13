import { useLocation, useRouter } from 'wouter-preact';
import { navigate } from "wouter/use-browser-location";

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
  const location = useLocation()[0];
  const { base } = useRouter();

  const baseParts = base.split('/');
  const parts = location.split('/').slice(baseParts.length - 1);

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

  const payload = breadcrumbs.map(crumb => breadCrumbItemHtml(crumb)).join('');

  for (const elt of document.querySelectorAll('header > .breadcrumbs .breadcrumb-item > a')) {
    elt.removeEventListener('click', followInternalLink);
  }
  
  document.querySelector('header > .breadcrumbs > ol.breadcrumb').innerHTML = payload;

  for (const crumb of breadcrumbs) {
    if (crumb.useLink) {
      document.getElementById(crumb.id)?.addEventListener('click', followInternalLink);
    }
  }

  //return html`<div>${ breadcrumbs.map(crumb => html`<span>| ${crumb.title}</span>`)}</div>`;
  return null;
}
