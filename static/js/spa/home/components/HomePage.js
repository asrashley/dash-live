import { html } from "htm/preact";
import { useContext } from "preact/hooks";
import { useComputed } from "@preact/signals";

import { routeMap } from "/libs/routemap.js";
import { AccordionFormGroup } from "@dashlive/ui";
import {
  useCombinedStreams,
  UseCombinedStreams,
} from "@dashlive/hooks";

import { ButtonRow } from './ButtonRow.js';
import { CgiInfoPanel } from './CgiInfoPanel.js';
import { ManifestUrl } from './ManifestUrl.js';
import { NoStreamsMessage } from './NoStreamsMessage.js';
import { useStreamOptions } from "../hooks/useStreamOptions.js";
import { StreamOptionsContext } from '../types/StreamOptionsHook.js';
import { useFieldGroups } from "../hooks/useFieldGroups.js";

function generateUrl(stdUrlFn, mpsUrlFn, mode, manifest, stream, nonDefaultOptions) {
  const url = new URL(stream.value.mps ?
    mpsUrlFn({
      mode: mode.value,
      manifest: manifest.value,
      mps_name: stream.value.value,
    }) : stdUrlFn({
      mode: mode.value,
      manifest: manifest.value,
      stream: stream.value.value,
    }),
    document.location.href
  );
  const query = new URLSearchParams(nonDefaultOptions.value);
  url.search = query.toString();
  return url;
}

function doNothing(ev) {
  ev.preventDefault();
  return false;
}

const formLayout = [2, 5, 5];

function StreamOptionsForm({data}) {
  const { setValue } = useContext(StreamOptionsContext);
  const { homeFieldGroups } = useFieldGroups();

  return html`<form name="mpsOptions" onSubmit=${doNothing}>
    <${AccordionFormGroup}
      groups=${homeFieldGroups.value}
      data=${data}
      expand="general"
      mode="cgi"
      setValue=${setValue}
      layout=${formLayout}
    />
  </form>`
}

export default function HomePage() {
  const combinedStreams = useCombinedStreams();
  const streamOptionsHook = useStreamOptions(combinedStreams);
  const { data, stream, mode, manifest, nonDefaultOptions, manifestOptions } = streamOptionsHook;
  const manifestUrl = useComputed(() =>
    generateUrl(routeMap.dashMpdV3.url, routeMap.mpsManifest.url, mode, manifest, stream, manifestOptions));
  const viewUrl = useComputed(() =>
    generateUrl(routeMap.viewManifest.url, routeMap.viewMpsManifest.url, mode, manifest, stream, manifestOptions));
  const manifestBaseName = useComputed(() => manifest.value.slice(0, -4));
  const videoUrl = useComputed(() =>
    generateUrl(routeMap.video.url, routeMap.videoMps.url, mode, manifestBaseName, stream, nonDefaultOptions));

  if (combinedStreams.loaded.value && combinedStreams.streamNames.value.length === 0) {
    return html`<div className="mb-3"><${NoStreamsMessage} /></div>`;
  }
  return html`<${UseCombinedStreams.Provider} value=${combinedStreams}>
    <${StreamOptionsContext.Provider} value=${streamOptionsHook}>
      <div>
        <${ManifestUrl} manifestUrl=${manifestUrl} />
        <div id="with-modules">
          <${ButtonRow} videoUrl=${videoUrl} viewUrl=${viewUrl} stream=${stream} />
          <${StreamOptionsForm} data=${data} />
        </div>
        <${CgiInfoPanel} />
      </div>
    </${StreamOptionsContext.Provider}>
  </${UseCombinedStreams.Provider}>`;
}

