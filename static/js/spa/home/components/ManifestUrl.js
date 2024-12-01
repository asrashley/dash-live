import { html } from "htm/preact";

export function ManifestUrl({ manifestUrl }) {
  return html` <div className="manifest-url rounded border">
    <span className="fw-semibold">Manifest URL: </span>
    <a id="dashurl" href="${manifestUrl.value}">
      ${manifestUrl.value.pathname}${manifestUrl.value.search}
    </a>
  </div>`;
}
