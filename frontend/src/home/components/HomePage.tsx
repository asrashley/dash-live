import { useCallback } from "preact/hooks";
import { type ReadonlySignal, useComputed, useSignal } from "@preact/signals";

import { routeMap, uiRouteMap } from "@dashlive/routemap";
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
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { StreamOptionsForm } from "./StreamOptionsForm";
import { ViewManifest } from "./ViewManifest";

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

export default function HomePage() {
  const combinedStreams = useCombinedStreams();
  const streamOptionsHook = useStreamOptions(combinedStreams);
  const viewing = useSignal<boolean>(false);
  const editUrl = useSignal<URL>();
  const { stream, mode, manifest, nonDefaultOptions, manifestOptions } = streamOptionsHook;
  const genManifest = useComputed<URL>(() => generateUrl(routeMap.dashMpdV3.url, routeMap.mpsManifest.url,
     mode, manifest, stream, manifestOptions));
  const manifestUrl = useComputed<URL>(() => viewing.value ? editUrl.value : genManifest.value);
  const manifestBaseName = useComputed<string>(() => manifest.value.slice(0, -4));
  const videoUrl = useComputed<URL>(() =>
    generateUrl(uiRouteMap.video.url,
      ({mode, manifest, mps_name: stream}) => uiRouteMap.video.url({mode: `mps-${mode}`, manifest, stream}),
      mode, manifestBaseName, stream, nonDefaultOptions));
  const setViewing = useCallback((flag: boolean) => {
    viewing.value = flag;
    editUrl.value = new URL(genManifest.value.href);
  }, [editUrl, genManifest, viewing]);
  const setManifestValue = useCallback((url: string) => {
    editUrl.value = new URL(url, document.location.href);
  }, [editUrl]);

  if (combinedStreams.loaded.value === false) {
    return <LoadingSpinner />;
  }
  if (combinedStreams.loaded.value && combinedStreams.streamNames.value.length === 0) {
    return <div className="mb-3"><NoStreamsMessage /></div>;
  }
  return <UseCombinedStreams.Provider value={combinedStreams}>
    <StreamOptionsContext.Provider value={streamOptionsHook}>
      <div>
        <ManifestUrl manifestUrl={manifestUrl} editable={viewing} setValue={setManifestValue} />
        <div id="with-modules">
          <ButtonRow videoUrl={videoUrl} stream={stream} viewing={viewing} setViewing={setViewing} />
          {viewing.value ? <ViewManifest manifestUrl={manifestUrl} /> : <StreamOptionsForm />}
        </div>
        <CgiInfoPanel />
      </div>
    </StreamOptionsContext.Provider>
  </UseCombinedStreams.Provider>;
}

