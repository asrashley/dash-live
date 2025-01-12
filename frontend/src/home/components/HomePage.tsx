import { useContext } from "preact/hooks";
import { type ReadonlySignal, Signal, useComputed } from "@preact/signals";

import { routeMap } from "@dashlive/routemap";
import { AccordionFormGroup } from "../../components/AccordionFormGroup";
import {
  CombinedStream,
  useCombinedStreams,
  UseCombinedStreams,
} from "../../hooks/useCombinedStreams";

import { ButtonRow } from './ButtonRow';
import { CgiInfoPanel } from './CgiInfoPanel';
import { ManifestUrl } from './ManifestUrl';
import { NoStreamsMessage } from './NoStreamsMessage';
import { useStreamOptions } from "../hooks/useStreamOptions";
import { StreamOptionsContext } from '../types/StreamOptionsHook';
import { useFieldGroups } from "../hooks/useFieldGroups";
import { InputFormData } from "../../types/InputFormData";

interface UrlGenFnProps {
  mode: string;
  manifest: string;
  stream?: string;
  mps_name?: string;
}

function generateUrl(
    stdUrlFn: (props: UrlGenFnProps) => string,
    mpsUrlFn: (props: UrlGenFnProps) => string,
    mode: ReadonlySignal<string>,
    manifest: ReadonlySignal<string>,
    stream: ReadonlySignal<CombinedStream>,
    nonDefaultOptions: ReadonlySignal<object>): URL {
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
  const query = new URLSearchParams(nonDefaultOptions.value as Record<string, string>);
  url.search = query.toString();
  return url;
}

function doNothing(ev: Event): boolean {
  ev.preventDefault();
  return false;
}

const formLayout = [2, 5, 5];

function StreamOptionsForm({data}: {data: Signal<InputFormData>}) {
  const { setValue } = useContext(StreamOptionsContext);
  const { homeFieldGroups } = useFieldGroups();

  return <form name="mpsOptions" onSubmit={doNothing}>
    <AccordionFormGroup
      groups={homeFieldGroups.value}
      data={data}
      expand="general"
      mode="cgi"
      setValue={setValue}
      layout={formLayout}
    />
  </form>;
}

export default function HomePage() {
  const combinedStreams = useCombinedStreams();
  const streamOptionsHook = useStreamOptions(combinedStreams);
  const { data, stream, mode, manifest, nonDefaultOptions, manifestOptions } = streamOptionsHook;
  const manifestUrl = useComputed<URL>(() =>
    generateUrl(routeMap.dashMpdV3.url, routeMap.mpsManifest.url, mode, manifest, stream, manifestOptions));
  const viewUrl = useComputed<URL>(() =>
    generateUrl(routeMap.viewManifest.url, routeMap.viewMpsManifest.url, mode, manifest, stream, manifestOptions));
  const manifestBaseName = useComputed<string>(() => manifest.value.slice(0, -4));
  const videoUrl = useComputed<URL>(() =>
    generateUrl(routeMap.video.url, routeMap.videoMps.url, mode, manifestBaseName, stream, nonDefaultOptions));

  if (combinedStreams.loaded.value && combinedStreams.streamNames.value.length === 0) {
    return <div className="mb-3"><NoStreamsMessage /></div>;
  }
  return <UseCombinedStreams.Provider value={combinedStreams}>
    <StreamOptionsContext.Provider value={streamOptionsHook}>
      <div>
        <ManifestUrl manifestUrl={manifestUrl} />
        <div id="with-modules">
          <ButtonRow videoUrl={videoUrl} viewUrl={viewUrl} stream={stream} />
          <StreamOptionsForm data={data} />
        </div>
        <CgiInfoPanel />
      </div>
    </StreamOptionsContext.Provider>
  </UseCombinedStreams.Provider>;
}

