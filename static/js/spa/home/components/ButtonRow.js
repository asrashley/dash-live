import { html } from "htm/preact";
import { useContext } from "preact/hooks";

import { Icon } from '@dashlive/ui';
import { StreamOptionsContext } from '../types/StreamOptionsHook.js';

export function ButtonRow({ videoUrl, viewUrl, stream }) {
  const { resetAllValues } = useContext(StreamOptionsContext);

  return html`<div className="d-flex flex-row align-self-stretch pb-3">
    <div className="play-button flex-fill text-center">
      <a className="btn btn-lg btn-primary fs-3" href="${videoUrl.value}">
        <${Icon} name="play-fill" />
        <span className="title ps-2">Play ${stream.value.title}</span>
      </a>
    </div>
    <div className="view-manifest-button flex-fill text-center">
      <a className="btn btn-lg btn-primary fs-3" href="${viewUrl.value}">
        <${Icon} name="search" className="pe-2" />View Manifest
      </a>
    </div>
    <div className="reset-all-button flex-fill text-center">
      <button className="btn btn-lg btn-primary fs-3" onClick=${resetAllValues}>
        <${Icon} name="trash3-fill" className="pe-2" />Reset Options
      </button>
    </div>
  </div>`;
}
