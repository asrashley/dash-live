import { type ReadonlySignal } from "@preact/signals";
import { useContext } from "preact/hooks";

import { Icon } from '../../components/Icon';
import { StreamOptionsContext } from '../types/StreamOptionsHook';
import { CombinedStream } from "../../hooks/useCombinedStreams";

interface ButtonRowProps {
   videoUrl: ReadonlySignal<URL>;
   viewUrl: ReadonlySignal<URL>;
   stream: ReadonlySignal<CombinedStream>;
}

export function ButtonRow({ videoUrl, viewUrl, stream }: ButtonRowProps) {
  const { resetAllValues } = useContext(StreamOptionsContext);

  return <div className="d-flex flex-row align-self-stretch pb-3">
    <div className="play-button flex-fill text-center">
      <a className="btn btn-lg btn-primary" href={videoUrl.value.href}>
        <Icon name="play-fill" />
        <span className="title ps-2">Play {stream.value.title}</span>
      </a>
    </div>
    <div className="view-manifest-button flex-fill text-center">
      <a className="btn btn-lg btn-primary" href={viewUrl.value.href}>
        <Icon name="search" className="pe-2" />View Manifest
      </a>
    </div>
    <div className="reset-all-button flex-fill text-center">
      <button className="btn btn-lg btn-primary" onClick={resetAllValues}>
        <Icon name="trash3-fill" className="pe-2" />Reset Options
      </button>
    </div>
  </div>;
}
