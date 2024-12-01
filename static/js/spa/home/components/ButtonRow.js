import { html } from "htm/preact";

export function ButtonRow({ videoUrl, viewUrl, stream }) {
  return html`<div className="row">
    <div className="play-button col-6">
      <a className="btn btn-primary selected-stream" href="${videoUrl.value}">
        <span className="bi bi-play-fill" aria-hidden="true" />
        <span className="title">Play ${stream.value.title}</span>
      </a>
    </div>
    <div className="col-6 view-manifest-button">
      <a className="view-manifest btn btn-light" href="${viewUrl.value}">
        <span class="bi bi-search icon"></span>View Manifest
      </a>
    </div>
  </div>`;
}
